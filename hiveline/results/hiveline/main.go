package main

import (
	"fmt"
	"github.com/uber/h3-go/v4"
	"time"
)

func main() {
	getModalShareContributionByOrigin()
}

func getModalShareContributionByOrigin() {
	simId := "eef0781a-dce2-4094-8f70-7c41351dc8c5"
	cache := "./cache"

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

	stats := make(map[string]*JourneyStats)

	for _, option := range selected {
		originTile := h3.LatLngToCell(h3.LatLng{Lat: option.Origin[1], Lng: option.Origin[0]}, 8)
		originTileStr := originTile.String()

		traceStats := getTraceStats(extractTrace(option))

		if traceStats.IsEmpty() {
			continue
		}

		if _, ok := stats[originTileStr]; !ok {
			stats[originTileStr] = &JourneyStats{}
		}

		stats[originTileStr] = stats[originTileStr].Add(traceStats)
	}

	total := 0.0

	for _, stat := range stats {
		carPm := stat.CarMeters * stat.CarPassengers
		railPm := stat.RailMeters * stat.RailPassengers
		busPm := stat.BusMeters * stat.BusPassengers
		walkPm := stat.WalkMeters * stat.Walkers

		total += carPm + railPm + busPm + walkPm
	}

	if total == 0 {
		panic("total is zero")
	}

	result := make(map[string]*TransportShares)

	for tileStr, stat := range stats {
		carPm := stat.CarMeters * stat.CarPassengers
		railPm := stat.RailMeters * stat.RailPassengers
		busPm := stat.BusMeters * stat.BusPassengers
		walkPm := stat.WalkMeters * stat.Walkers

		shares := &TransportShares{
			Car:  carPm / total,
			Rail: railPm / total,
			Bus:  busPm / total,
			Walk: walkPm / total,
		}

		result[tileStr] = shares
	}

	fmt.Println("got", len(result), "results in", time.Since(t))

	err = writeJSON(cache+"/modal-heatmaps/contribution-origin-"+simId+".json", result)
	if err != nil {
		panic(err)
	}
}

func getModalShareByOrigin() {
	simId := "eef0781a-dce2-4094-8f70-7c41351dc8c5"
	cache := "./cache"

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

	stats := make(map[string]*JourneyStats)

	for _, option := range selected {
		originTile := h3.LatLngToCell(h3.LatLng{Lat: option.Origin[1], Lng: option.Origin[0]}, 8)
		originTileStr := originTile.String()

		traceStats := getTraceStats(extractTrace(option))

		if traceStats.IsEmpty() {
			continue
		}

		if _, ok := stats[originTileStr]; !ok {
			stats[originTileStr] = &JourneyStats{}
		}

		stats[originTileStr] = stats[originTileStr].Add(traceStats)
	}

	result := make(map[string]*TransportShares)

	for tileStr, stat := range stats {
		result[tileStr] = stat.GetShares()
	}

	fmt.Println("got", len(result), "results in", time.Since(t))

	err = writeJSON(cache+"/modal-heatmaps/origin-"+simId+".json", result)
	if err != nil {
		panic(err)
	}
}

func getHeatmap() {
	simId := "0e952d41-9b3d-4bd3-8514-fabefe1549e1"
	cache := "./cache"

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

	tiles := getTilesFromTraces(traces)

	fmt.Println("got", len(tiles), "tiles in", time.Since(t))
	t = time.Now()

	result := make(map[string]*TransportShares)

	for _, tile := range tiles {
		filtered := filterTraces(traces, tile.Bounds)

		stats := getStats(filtered)

		if stats.IsEmpty() {
			continue
		}

		result[tile.Cell.String()] = stats.GetShares()
	}

	fmt.Println("got", len(result), "results in", time.Since(t))

	err = writeJSON(cache+"/modal-heatmaps/"+simId+".json", result)
	if err != nil {
		panic(err)
	}
}
