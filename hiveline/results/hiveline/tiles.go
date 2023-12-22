package main

import (
	"github.com/paulmach/orb"
	"github.com/paulmach/orb/planar"
	"github.com/uber/h3-go/v4"
)

type Tile struct {
	Cell   h3.Cell
	Bounds PolyBounds
}

func getCellPolygon(cell h3.Cell) orb.Polygon {
	points := make([]orb.Point, 7)
	boundary := cell.Boundary()

	for i := 0; i < 6; i++ {
		points[i] = orb.Point{boundary[i].Lng, boundary[i].Lat}
	}

	points[6] = points[0]

	return orb.Polygon{points}
}

type Bounds interface {
	Contains(point orb.Point) bool
}

type MultiPolyBounds []PolyBounds

func (b MultiPolyBounds) Contains(point orb.Point) bool {
	for _, poly := range b {
		if poly.Contains(point) {
			return true
		}
	}

	return false
}

type PolyBounds struct {
	Geometry orb.Polygon
	Bounds   orb.Bound
}

func (b PolyBounds) Contains(point orb.Point) bool {
	if !b.Bounds.Contains(point) {
		return false
	}

	return planar.PolygonContains(b.Geometry, point)
}

func getPolyBounds(poly orb.Polygon) PolyBounds {
	bounds := poly.Bound()

	return PolyBounds{
		Geometry: poly,
		Bounds:   bounds,
	}
}
