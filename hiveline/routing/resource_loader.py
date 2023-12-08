import time
from datetime import datetime
from urllib.parse import urlparse, parse_qs, urljoin

import bson
import requests
from bs4 import BeautifulSoup, NavigableString

from hiveline.mongo.db import get_database


def __extract_geo_fabrik(base_url):
    response = requests.get(base_url)

    soup = BeautifulSoup(response.content, 'html.parser')

    options = soup.select("#details table tr")

    first = True

    links = []

    for title in options:
        if first:
            first = False
            continue

        columns = title.find_all("td")
        file_name = columns[0].get_text()

        if not file_name.endswith(".osm.pbf"):
            continue

        if file_name.endswith("-latest.osm.pbf"):  # not a permalink, date may change
            continue

        relative_link = columns[0].find("a")["href"]
        link = urljoin(base_url, relative_link)

        date_str = columns[1].get_text()
        date = datetime.strptime(date_str, "%Y-%m-%d %H:%M")

        links.append({"date": date, "link": link})

    return links


def __extract_provider_page_feeds(base_url):
    print("visiting " + base_url + "...")

    # get page from base_url
    parsed = urlparse(base_url)
    parsed_query = parse_qs(parsed.query)

    page = 1

    if "p" in parsed_query:
        page = int(parsed_query["p"][0])

    response = requests.get(base_url)
    soup = BeautifulSoup(response.content, 'html.parser')

    links = []

    datasets = soup.select("div.panel table.table tbody tr")

    for dataset in datasets:
        columns = dataset.find_all("td")
        date_string = columns[0].get_text().strip()  # for example: 17 November 2022

        date = datetime.strptime(date_string, "%d %B %Y")
        date_url_str = date.strftime("%Y%m%d")

        link = "https://" + parsed.netloc + parsed.path + "/" + date_url_str + "/download"

        links.append({"date": date, "link": link})

    page_buttons = soup.select("nav ul.pagination li a")

    if len(page_buttons) <= page:
        return links

    # go to next page
    next_page_link = "https://" + parsed.netloc + parsed.path + "?p=" + str(page + 1)

    time.sleep(1)  # don't spam the server

    return links + __extract_provider_page_feeds(next_page_link)


def __extract_provider_transit_feeds(base_url):
    print("visiting " + base_url + "...")

    response = requests.get(base_url)

    soup = BeautifulSoup(response.content, 'html.parser')

    links = {}

    providers = soup.select("div.panel div.list-group a.list-group-item")

    for provider in providers:
        category = provider.find("span", {"class": "badge"}).get_text().strip()
        if category != "GTFS":
            continue
        name = ' '.join([x.strip() for x in provider if isinstance(x, NavigableString)])  # outer text
        relative_link = provider["href"].strip()

        # link is relative to website, so we need to convert it to absolute
        link = urljoin(base_url, relative_link)

        time.sleep(1)  # don't spam the server

        links[name] = __extract_provider_page_feeds(link)

    return links


def __extract_location_transit_feeds(base_url):
    print("visiting " + base_url + "...")

    response = requests.get(base_url)

    soup = BeautifulSoup(response.content, 'html.parser')

    location_name = soup.find("h1").get_text()

    providers = soup.select("table tbody tr")

    links = {}

    for provider in providers:
        columns = provider.find_all("td")
        provider_link = columns[0].find("a")

        relative_link = provider_link["href"]
        name = provider_link.get_text().strip()

        # link is relative to website, so we need to convert it to absolute
        link = urljoin(base_url, relative_link)

        time.sleep(1)  # don't spam the server

        link_map = __extract_provider_transit_feeds(link)

        for key, value in link_map.items():
            links[name + " // " + key] = value

    return links, location_name


# todo: support mobidatalab, transit.land, navitia, ...
def create_place_resources(geofabrik_url=None, transitfeeds_url=None, place_name=None, place_id=None, db=None,
                           skip_existing=False):
    """
    Extracts the links from given web pages and puts them into the database. At least one of geofabrik_url and
    transitfeeds_url should be set. If place_id is set, skip_existing=True and the document already exists, the
    function will return the existing document.

    :param geofabrik_url: The url to the geofabrik page of the location. For example
           https://download.geofabrik.de/europe/ireland-and-northern-ireland.html
    :param transitfeeds_url: The url to the transitfeeds.com page of the location. For example
           https://transitfeeds.com/l/579-dublin-ireland
    :param place_name: The name of the place. If not set, the name will be extracted from the transitfeeds page.
    :param place_id: The id of the place. If not set, a random id will be generated.
    :param db: The database to use. If not set, the default database will be used.
    :param skip_existing: If true, the function will not overwrite existing entries in the database.
    :return:
    """
    if db is None:
        db = get_database()

    res = db["place-resources"]

    if skip_existing and res.count_documents({"place-id": place_id}) > 0:
        return res.find_one({"place-id": place_id})

    if geofabrik_url is None and transitfeeds_url is None:
        raise ValueError("At least one of geofabrik_url and transitfeeds_url must be set")

    osm_links = __extract_geo_fabrik(geofabrik_url) if geofabrik_url is not None else []
    gtfs_links = []
    location_name = None

    if transitfeeds_url is not None:
        gtfs_links, location_name = __extract_location_transit_feeds(
            transitfeeds_url)

    if place_name is not None:
        location_name = place_name

    if place_id is None:
        place_id = bson.ObjectId()

    if isinstance(place_id, str):
        place_id = bson.ObjectId(place_id)

    doc = {
        "osm": osm_links,
        "gtfs": gtfs_links,
        "place-name": location_name,
        "place-id": place_id,
        "geofabrik": geofabrik_url,
        "transitfeed": transitfeeds_url
    }

    print("created document")
    print(doc)

    res.insert_one(doc)

    return doc


if __name__ == "__main__":
    gf_url = "https://download.geofabrik.de/europe/germany/bayern/oberbayern.html"
    tf_url = "https://transitfeeds.com/l/734-munich-germany"
    create_place_resources(gf_url, tf_url)
