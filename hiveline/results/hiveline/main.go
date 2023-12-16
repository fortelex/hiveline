package main

import (
	"context"
	"encoding/json"
	"fmt"
	"github.com/Vector-Hector/fptf"
	"github.com/Vector-Hector/goutil"
	"github.com/joho/godotenv"
	"github.com/paulmach/orb"
	"github.com/paulmach/orb/geo"
	"github.com/paulmach/orb/geojson"
	"github.com/paulmach/orb/planar"
	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/mongo"
	"go.mongodb.org/mongo-driver/mongo/options"
	"io"
	"os"
	"time"
)

func main() {
	simId := "bd6809da-8113-469f-91cc-501549e8df68"
	cache := "./cache"

	boundary, err := readBoundary(cache + "/place-bounds/eindhoven.json")
	if err != nil {
		panic(err)
	}

	t := time.Now()

	results, err := getResults(simId, cache)
	if err != nil {
		panic(err)
	}

	fmt.Println("got", len(results), "results in", time.Since(t))
	t = time.Now()

	selected := getSelected(results)

	fmt.Println("got", len(selected), "selected in", time.Since(t))
	t = time.Now()

	traces := getTraces(selected)

	fmt.Println("got", len(traces), "traces in", time.Since(t))
	t = time.Now()

	traces = filterTraces(traces, boundary)

	fmt.Println("got", len(traces), "filtered traces in", time.Since(t))
	t = time.Now()

	stats := getStats(traces)

	fmt.Println("got stats in", time.Since(t))
	t = time.Now()

	util.PrintJSON(stats)
	util.PrintJSON(stats.GetShares())
}

type TransportShares struct {
	Car  float64
	Rail float64
	Bus  float64
	Walk float64
}

type JourneyStats struct {
	CarMeters  float64
	RailMeters float64
	BusMeters  float64
	WalkMeters float64

	CarPassengers  float64
	RailPassengers float64
	BusPassengers  float64
	Walkers        float64
}

func (s *JourneyStats) Add(other *JourneyStats) *JourneyStats {
	return &JourneyStats{
		CarMeters:  s.CarMeters + other.CarMeters,
		RailMeters: s.RailMeters + other.RailMeters,
		BusMeters:  s.BusMeters + other.BusMeters,
		WalkMeters: s.WalkMeters + other.WalkMeters,

		CarPassengers:  s.CarPassengers + other.CarPassengers,
		RailPassengers: s.RailPassengers + other.RailPassengers,
		BusPassengers:  s.BusPassengers + other.BusPassengers,
		Walkers:        s.Walkers + other.Walkers,
	}
}

func (s *JourneyStats) GetShares() *TransportShares {
	carPm := s.CarMeters * s.CarPassengers
	railPm := s.RailMeters * s.RailPassengers
	busPm := s.BusMeters * s.BusPassengers
	walkPm := s.WalkMeters * s.Walkers

	total := carPm + railPm + busPm + walkPm

	return &TransportShares{
		Car:  carPm / total,
		Rail: railPm / total,
		Bus:  busPm / total,
		Walk: walkPm / total,
	}
}

func getStats(traces []Trace) *JourneyStats {
	stats := &JourneyStats{}

	for _, trace := range traces {
		if len(trace) < 2 {
			continue
		}
		stats = stats.Add(getTraceStats(trace))
	}

	return stats
}

func getTraceStats(trace Trace) *JourneyStats {
	stats := &JourneyStats{}

	for i, toElem := range trace[1:] {
		fromElem := trace[i]

		if fromElem.Mode != toElem.Mode {
			continue
		}

		dist := geo.Distance(toElem.Point, fromElem.Point)
		pax := 1.0
		if !fromElem.IsLegStart {
			pax = 0
		}

		switch fromElem.Mode {
		case fptf.ModeTrain:
			fallthrough
		case fptf.ModeGondola:
			fallthrough
		case fptf.ModeWatercraft:
			stats.RailMeters += dist
			stats.RailPassengers += pax
			break
		case fptf.ModeBus:
			stats.BusMeters += dist
			stats.BusPassengers += pax
			break
		case fptf.ModeCar:
			stats.CarMeters += dist
			stats.CarPassengers += pax
			break
		case fptf.ModeWalking:
			stats.WalkMeters += dist
			stats.Walkers += pax
			break
		default:
			fmt.Println("unknown mode:", fromElem.Mode)
		}
	}

	if stats.CarPassengers > 1 {
		fmt.Println("car with passengers:", stats.CarPassengers)
		util.PrintJSON(trace)
	}

	return stats
}

type TraceElement struct {
	Point      orb.Point
	Time       time.Time
	Mode       fptf.Mode
	IsLegStart bool
}

type Trace []TraceElement

func filterTrace(trace Trace, boundary orb.MultiPolygon) Trace {
	filtered := make(Trace, 0)
	carryLegStart := false

	for _, elem := range trace {
		isLegStart := elem.IsLegStart
		cont := planar.MultiPolygonContains(boundary, elem.Point)
		if cont {
			isLegStart = isLegStart || carryLegStart
			carryLegStart = false
			filtered = append(filtered, TraceElement{
				Point:      elem.Point,
				Time:       elem.Time,
				Mode:       elem.Mode,
				IsLegStart: isLegStart,
			})
			continue
		}

		if isLegStart {
			carryLegStart = true
		}
	}

	return filtered
}

func filterTraces(traces []Trace, boundary orb.MultiPolygon) []Trace {
	filtered := make([]Trace, len(traces))

	theadCount := 12

	done := make(chan bool, theadCount)

	for i := 0; i < theadCount; i++ {
		go func(i int) {
			for j := i; j < len(traces); j += theadCount {
				filtered[j] = filterTrace(traces[j], boundary)
			}
			done <- true
		}(i)
	}

	for i := 0; i < theadCount; i++ {
		<-done
	}

	return filtered
}

func locToPoint(loc *fptf.Location) orb.Point {
	return orb.Point{loc.Longitude, loc.Latitude}
}

func extractTrace(journey *fptf.Journey) Trace {
	trace := make(Trace, 0)

	for _, leg := range journey.Trips {
		if len(leg.Stopovers) == 0 {
			originLoc := leg.Origin.GetLocation()
			destLoc := leg.Destination.GetLocation()

			if originLoc != nil && destLoc != nil {
				trace = append(trace, TraceElement{
					Point:      locToPoint(originLoc),
					Time:       leg.Departure.Time,
					Mode:       leg.Mode,
					IsLegStart: true,
				})

				trace = append(trace, TraceElement{
					Point:      locToPoint(destLoc),
					Time:       leg.Arrival.Time,
					Mode:       leg.Mode,
					IsLegStart: false,
				})
			}

			continue
		}

		for i, stopover := range leg.Stopovers {
			loc := stopover.StopStation.GetLocation()
			if loc == nil {
				continue
			}

			t := stopover.Departure
			if t.IsZero() {
				t = stopover.Arrival
			}

			trace = append(trace, TraceElement{
				Point:      locToPoint(loc),
				Time:       stopover.Departure.Time,
				Mode:       leg.Mode,
				IsLegStart: i == 0,
			})
		}
	}

	return trace
}

func getSelectedOption(result *RouteResult) *RouteOption {
	var selected *RouteOption
	var duration time.Duration

	wouldUseCar := result.Traveller.WouldUseCar()

	for _, option := range result.Options {
		if !wouldUseCar && option.IsCar() {
			continue
		}

		dep := option.Journey.GetDeparture()
		depDelay := option.Journey.GetDepartureDelay()
		if depDelay != nil {
			dep = dep.Add(time.Duration(*depDelay) * time.Second)
		}

		arr := option.Journey.GetArrival()
		arrDelay := option.Journey.GetArrivalDelay()
		if arrDelay != nil {
			arr = arr.Add(time.Duration(*arrDelay) * time.Second)
		}

		dur := arr.Sub(dep)

		if selected == nil || dur < duration {
			selected = option
			duration = dur
		}
	}

	return selected
}

func getTraces(options []*RouteOption) []Trace {
	traces := make([]Trace, len(options))

	for i, option := range options {
		traces[i] = extractTrace(&option.Journey.Journey)
	}

	return traces
}

func getSelected(results []*RouteResult) []*RouteOption {
	selected := make([]*RouteOption, 0, len(results))

	for _, result := range results {
		opt := getSelectedOption(result)
		if opt != nil {
			selected = append(selected, opt)
		}
	}

	return selected
}

func readJSON(path string, target any) error {
	file, err := os.Open(path)
	if err != nil {
		return err
	}

	defer file.Close()

	data, err := io.ReadAll(file)
	if err != nil {
		return err
	}

	return json.Unmarshal(data, target)
}

func writeJSON(path string, source any) error {
	data, err := json.Marshal(source)
	if err != nil {
		return err
	}

	err = os.WriteFile(path, data, 0644)
	if err != nil {
		return err
	}

	return nil
}

func getResults(simId string, cache string) ([]*RouteResult, error) {
	cacheFile := cache + "/hiveline-journeys/" + simId + ".json"

	if _, err := os.Stat(cacheFile); !os.IsNotExist(err) {
		fmt.Println("reading from cache")

		var results []*RouteResult
		err = readJSON(cacheFile, &results)
		if err != nil {
			return nil, err
		}

		return results, nil
	}

	client, database := getDatabase()

	defer func() {
		if err := client.Disconnect(context.Background()); err != nil {
			panic(err)
		}
	}()

	db := client.Database(database)

	coll := db.Collection("route-results")

	cur, err := coll.Find(context.Background(), bson.M{
		"sim-id": simId,
	})
	if err != nil {
		return nil, err
	}

	defer cur.Close(context.Background())

	var results []*RouteResult
	err = cur.All(context.Background(), &results)
	if err != nil {
		return nil, err
	}

	err = writeJSON(cacheFile, results)
	if err != nil {
		return nil, err
	}

	return results, nil
}

func readBoundary(path string) (orb.MultiPolygon, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, err
	}

	defer file.Close()

	data, err := io.ReadAll(file)
	if err != nil {
		return nil, err
	}

	fc, err := geojson.UnmarshalFeatureCollection(data)
	if err != nil {
		return nil, err
	}

	polygons := make([]orb.Polygon, 0)

	for _, feature := range fc.Features {
		geom := feature.Geometry
		if geom == nil {
			continue
		}

		polygon, ok := geom.(orb.Polygon)
		if ok {
			polygons = append(polygons, polygon)
			continue
		}

		multiPolygon, ok := geom.(orb.MultiPolygon)
		if ok {
			polygons = append(polygons, multiPolygon...)
			continue
		}
	}

	return polygons, nil
}

type Journey struct {
	fptf.Journey
}

func (j *Journey) UnmarshalBSON(data []byte) error {
	var raw map[string]interface{}
	err := bson.Unmarshal(data, &raw)
	if err != nil {
		return err
	}

	data, err = json.Marshal(raw)
	if err != nil {
		return err
	}

	j.Journey = fptf.Journey{}
	err = json.Unmarshal(data, &j.Journey)
	if err != nil {
		return err
	}

	return nil
}

type RouteOption struct {
	RouteOptionId string      `bson:"route-option-id" json:"route-option-id"`
	Origin        []float64   `bson:"origin" json:"origin"`
	Destination   []float64   `bson:"destination" json:"destination"`
	Departure     time.Time   `bson:"departure" json:"departure"`
	Modes         []fptf.Mode `bson:"modes" json:"modes"`
	Journey       Journey     `bson:"journey" json:"journey"`
}

func (r *RouteOption) IsCar() bool {
	for _, trip := range r.Journey.Trips {
		mode := trip.GetMode()

		if mode != nil && *mode == fptf.ModeCar {
			return true
		}
	}

	return false
}

type Vehicles struct {
	Car       *int    `json:"car" bson:"car"`
	Moto      *int    `json:"moto" bson:"moto"`
	Utilities *int    `json:"utilities" bson:"utilities"`
	Usage     *string `json:"usage" bson:"usage"`
}

type Traveller struct {
	Employed       bool      `json:"employed" bson:"employed"`
	EmploymentType *string   `json:"employment_type" bson:"employment_type"`
	Vehicles       Vehicles  `json:"vehicles" bson:"vehicles"`
	Age            string    `json:"age" bson:"age"`
	VcCreated      time.Time `json:"vc-created" bson:"vc-created"`
}

func (t *Traveller) WouldUseCar() bool {
	if t.Vehicles.Usage == nil {
		return false
	}

	return true
}

type RouteResult struct {
	DocId     string                 `bson:"_id" json:"id"`
	VcId      string                 `bson:"vc-id" json:"vc-id"`
	SimId     string                 `bson:"sim-id" json:"sim-id"`
	Traveller *Traveller             `bson:"traveller" json:"traveller"`
	Options   []*RouteOption         `bson:"options" json:"options"`
	Meta      map[string]interface{} `bson:"meta" json:"meta"`
}

func getDatabase() (*mongo.Client, string) {

	err := godotenv.Load()
	if err != nil {
		panic(err)
	}

	user := os.Getenv("UP_MONGO_USER")
	password := os.Getenv("UP_MONGO_PASSWORD")
	domain := os.Getenv("UP_MONGO_DOMAIN")
	database := os.Getenv("UP_MONGO_DATABASE")

	connectionString := fmt.Sprintf("mongodb://%s:%s@%s/%s?authSource=admin", user, password, domain, database)

	client, err := mongo.Connect(context.Background(), options.Client().ApplyURI(connectionString))
	if err != nil {
		panic(err)
	}

	return client, database
}
