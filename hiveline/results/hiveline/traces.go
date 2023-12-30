package main

import (
	"github.com/Vector-Hector/fptf"
	"github.com/paulmach/orb"
	"github.com/twpayne/go-polyline"
	"github.com/uber/h3-go/v4"
	"time"
)

type TraceElement struct {
	Point      orb.Point
	Time       time.Time
	Mode       fptf.Mode
	IsLegStart bool
}

func (t *TraceElement) Dimensions() int {
	return 2
}

func (t *TraceElement) Dimension(i int) float64 {
	return t.Point[i]
}

type Trace struct {
	VcId          string
	RouteOptionId string
	Trace         []TraceElement
}

func filterTrace(trace Trace, boundary Bounds) Trace {
	contains := make([]bool, len(trace.Trace))

	for i, elem := range trace.Trace {
		contains[i] = boundary.Contains(elem.Point)
	}

	filtered := make([]TraceElement, 0)
	carryLegStart := false

	for i, elem := range trace.Trace {
		isLegStart := elem.IsLegStart
		cont := contains[i]

		// also include points next to the boundary
		if i > 0 && contains[i-1] && !cont {
			cont = true
		}
		if i < len(trace.Trace)-1 && contains[i+1] && !cont {
			cont = true
		}

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

	return Trace{
		VcId:          trace.VcId,
		RouteOptionId: trace.RouteOptionId,
		Trace:         filtered,
	}
}

func filterTracesByBounds(traces []Trace, boundary Bounds) []Trace {
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

func downSampleTraces(traces []Trace, targetCount int) []Trace {
	downSampled := make([]Trace, len(traces))

	theadCount := 12

	done := make(chan bool, theadCount)

	for i := 0; i < theadCount; i++ {
		go func(i int) {
			for j := i; j < len(traces); j += theadCount {
				downSampled[j] = downSampleTrace(traces[j], targetCount)
			}
			done <- true
		}(i)
	}

	for i := 0; i < theadCount; i++ {
		<-done
	}

	return downSampled
}

func downSampleTrace(trace Trace, targetCount int) Trace {
	if len(trace.Trace) <= targetCount {
		return trace
	}

	nonLegStartCount := 0
	for _, elem := range trace.Trace {
		if !elem.IsLegStart {
			nonLegStartCount++
		}
	}

	if nonLegStartCount <= targetCount {
		return trace
	}

	downSampled := make([]TraceElement, 0)

	ratio := float64(targetCount) / float64(nonLegStartCount) // this is always < 1
	buildUp := 0.0

	for _, elem := range trace.Trace {
		if elem.IsLegStart {
			downSampled = append(downSampled, elem)
			continue
		}

		buildUp += ratio

		if buildUp >= 1.0 {
			downSampled = append(downSampled, elem)
			buildUp -= 1.0
		}
	}

	return Trace{
		VcId:          trace.VcId,
		RouteOptionId: trace.RouteOptionId,
		Trace:         downSampled,
	}
}

func locToPoint(loc *fptf.Location) orb.Point {
	return orb.Point{loc.Longitude, loc.Latitude}
}

func extractTrace(option *RouteOption) Trace {
	trace := make([]TraceElement, 0)

	for _, leg := range option.Journey.Trips {
		if leg.Polyline != "" {
			legTrace, _, err := polyline.DecodeCoords([]byte(leg.Polyline))
			if err == nil {
				start := leg.Departure.Time
				dt := leg.Arrival.Time.Sub(start) / time.Duration(len(legTrace))
				for i, point := range legTrace {
					trace = append(trace, TraceElement{
						Point:      orb.Point{point[1], point[0]},
						Time:       start.Add(time.Duration(i) * dt),
						Mode:       leg.Mode,
						IsLegStart: i == 0,
					})
				}
				continue
			}
		}

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

	return Trace{
		VcId:          option.vcId,
		RouteOptionId: option.RouteOptionId,
		Trace:         trace,
	}
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

	if selected == nil {
		return nil
	}

	selected.vcId = result.VcId
	return selected
}

func getTraces(options []*RouteOption) []Trace {
	traces := make([]Trace, len(options))

	for i, option := range options {
		traces[i] = extractTrace(option)
	}

	return traces
}

func getTilesFromTraces(traces []Trace) []Tile {
	tileIds := make(map[h3.Cell]bool)

	for _, trace := range traces {
		for _, elem := range trace.Trace {
			cell := h3.LatLngToCell(h3.LatLng{Lat: elem.Point[1], Lng: elem.Point[0]}, 8)
			tileIds[cell] = true
		}
	}

	tiles := make([]Tile, 0, len(tileIds))

	for cell := range tileIds {
		polygon := getCellPolygon(cell)
		boundary := getPolyBounds(polygon)
		tile := Tile{
			Cell:   cell,
			Bounds: boundary,
		}

		tiles = append(tiles, tile)
	}

	return tiles
}

type MongoTraces struct {
	VcId          string       `bson:"vc-id" json:"vc-id"`
	RouteOptionId string       `bson:"route-option-id" json:"route-option-id"`
	Traces        []MongoTrace `bson:"traces" json:"traces"`
}

type MongoTrace struct {
	Mode  fptf.Mode `bson:"mode" json:"mode"`
	Trace string    `bson:"trace" json:"trace"`
}

func getMongoTraces(trace Trace) MongoTraces {
	mTraces := make([]MongoTrace, 0)
	lastMode := fptf.Mode("")
	currentTrace := make([][]float64, 0)

	for _, point := range trace.Trace {
		if point.Mode != lastMode {
			if len(currentTrace) > 0 {
				mTraces = append(mTraces, MongoTrace{
					Mode:  lastMode,
					Trace: string(polyline.EncodeCoords(currentTrace)),
				})
			}

			lastMode = point.Mode
			currentTrace = make([][]float64, 0)
		}

		currentTrace = append(currentTrace, []float64{point.Point[1], point.Point[0]})
	}

	if len(currentTrace) > 0 {
		mTraces = append(mTraces, MongoTrace{
			Mode:  lastMode,
			Trace: string(polyline.EncodeCoords(currentTrace)),
		})
	}

	return MongoTraces{}
}
