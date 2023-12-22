package main

import (
	"context"
	"fmt"
	"github.com/Vector-Hector/fptf"
	"github.com/joho/godotenv"
	"github.com/uber/h3-go/v4"
	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/bson/primitive"
	"go.mongodb.org/mongo-driver/mongo"
	"go.mongodb.org/mongo-driver/mongo/options"
	"os"
	"time"
)

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

type Simulation struct {
	Id               primitive.ObjectID `bson:"_id" json:"id"`
	SimId            string             `bson:"sim-id" json:"sim-id"`
	PlaceId          primitive.ObjectID `bson:"place-id" json:"place-id"`
	SimDate          time.Time          `bson:"sim-date" json:"sim-date"`
	Created          time.Time          `bson:"created" json:"created"`
	CreatedBy        string             `bson:"created-by" json:"created-by"`
	CreatedFromSimId string             `bson:"created-from-sim-id" json:"created-from-sim-id"`
}

type Place struct {
	Id      primitive.ObjectID `bson:"_id" json:"id"`
	Name    string             `bson:"name" json:"name"`
	Country string             `bson:"country" json:"country"`
	Shape   string             `bson:"shape" json:"shape"`
	Bbox    string             `bson:"bbox" json:"bbox"`
	Tiles   []int64            `bson:"tiles" json:"tiles"`
	Nuts3   []string           `bson:"nuts-3" json:"nuts-3"`
}

func getTiles(simId string) ([]Tile, error) {
	client, database := getDatabase()

	defer func() {
		if err := client.Disconnect(context.Background()); err != nil {
			panic(err)
		}
	}()

	db := client.Database(database)

	var sim Simulation
	err := db.Collection("simulations").FindOne(context.Background(), bson.M{
		"sim-id": simId,
	}).Decode(&sim)
	if err != nil {
		return nil, err
	}

	var place Place
	err = db.Collection("places").FindOne(context.Background(), bson.M{
		"_id": sim.PlaceId,
	}).Decode(&place)
	if err != nil {
		return nil, err
	}

	tiles := make([]Tile, len(place.Tiles))

	for i, tile := range place.Tiles {
		cell := h3.Cell(tile)
		polygon := getCellPolygon(cell)
		boundary := getPolyBounds(polygon)
		tiles[i] = Tile{
			Cell:   cell,
			Bounds: boundary,
		}
	}

	return tiles, nil
}

type RouteOption struct {
	RouteOptionId string       `bson:"route-option-id" json:"route-option-id"`
	Origin        []float64    `bson:"origin" json:"origin"`
	Destination   []float64    `bson:"destination" json:"destination"`
	Departure     time.Time    `bson:"departure" json:"departure"`
	Modes         []fptf.Mode  `bson:"modes" json:"modes"`
	Journey       fptf.Journey `bson:"journey" json:"journey"`
	vcId          string
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
