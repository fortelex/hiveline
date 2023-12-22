package main

import (
	"fmt"
	"github.com/Vector-Hector/fptf"
	"github.com/paulmach/orb/geo"
)

type TransportShares struct {
	Car  float64 `json:"car"`
	Rail float64 `json:"rail"`
	Bus  float64 `json:"bus"`
	Walk float64 `json:"walk"`
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

func (s *JourneyStats) IsEmpty() bool {
	return s.CarMeters == 0 &&
		s.RailMeters == 0 &&
		s.BusMeters == 0 &&
		s.WalkMeters == 0 &&
		s.CarPassengers == 0 &&
		s.RailPassengers == 0 &&
		s.BusPassengers == 0 &&
		s.Walkers == 0
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

	if total == 0 {
		return &TransportShares{}
	}

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
		if len(trace.Trace) < 2 {
			continue
		}
		stats = stats.Add(getTraceStats(trace))
	}

	return stats
}

func getTraceStats(trace Trace) *JourneyStats {
	stats := &JourneyStats{}

	for i, toElem := range trace.Trace[1:] {
		fromElem := trace.Trace[i]

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
		//util.PrintJSON(trace)
	}

	return stats
}
