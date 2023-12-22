package main

import (
	"encoding/json"
	"github.com/paulmach/orb"
	"github.com/paulmach/orb/geojson"
	"io"
	"os"
	"path/filepath"
)

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
	dirPath := filepath.Dir(path)

	if _, err := os.Stat(dirPath); os.IsNotExist(err) {
		err = os.MkdirAll(dirPath, 0755)
		if err != nil {
			return err
		}
	}

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

func readBoundary(path string) (MultiPolyBounds, error) {
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

	polygons := make([]PolyBounds, 0)

	for _, feature := range fc.Features {
		geom := feature.Geometry
		if geom == nil {
			continue
		}

		polygon, ok := geom.(orb.Polygon)
		if ok {
			polygons = append(polygons, getPolyBounds(polygon))
			continue
		}

		multiPolygon, ok := geom.(orb.MultiPolygon)
		if ok {
			for _, poly := range multiPolygon {
				polygons = append(polygons, getPolyBounds(poly))
			}
			continue
		}
	}

	return polygons, nil
}
