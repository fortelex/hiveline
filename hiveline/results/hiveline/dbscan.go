package main

import "github.com/kyroy/kdtree"

// Point represents a cluster point which can measure distance to another point.
type Point interface {
	kdtree.Point
	Name() string
	DistanceTo(Point) float64
}

func Cluster[T Point](minDensity int, epsilon float64, k int, points ...T) (clusters [][]T) {
	kdtreePoints := make([]kdtree.Point, len(points))
	for i, point := range points {
		kdtreePoints[i] = point
	}
	tree := kdtree.New(kdtreePoints)

	return ClusterWithTree(minDensity, epsilon, k, tree, points...)
}

func ClusterWithTree[T Point](minDensity int, epsilon float64, k int, tree *kdtree.KDTree, points ...T) (clusters [][]T) {
	visited := make(map[string]bool, len(points))
	for i, point := range points {
		if i%10000 == 0 {
			println("clustering", i, "/", len(points))
		}
		neighbours := findNeighboursInTree(point, tree, k, epsilon)
		//neighbours := findNeighbours(point, points, epsilon)
		if len(neighbours)+1 >= minDensity {
			visited[point.Name()] = true
			cluster := []T{point}
			cluster = expandCluster(cluster, neighbours, visited, minDensity, epsilon)

			if len(cluster) >= minDensity {
				clusters = append(clusters, cluster)
			}
		} else {
			visited[point.Name()] = false
		}
	}
	return clusters
}

// Finds the neighbours from given array, depends on epsolon , which determines
// the distance limit from the point
func findNeighboursInTree[T Point](point T, points *kdtree.KDTree, k int, epsilon float64) []T {
	neighbours := make([]T, 0)

	for _, neighbour := range points.KNN(point, k) {
		potNeigb := neighbour.(T)
		if point.Name() != potNeigb.Name() && potNeigb.DistanceTo(point) <= epsilon {
			neighbours = append(neighbours, potNeigb)
		}
	}

	return neighbours
}

// Finds the neighbours from given array, depends on epsolon , which determines
// the distance limit from the point
func findNeighbours[T Point](point T, points []T, epsilon float64) []T {
	neighbours := make([]T, 0)
	for _, potNeigb := range points {
		if point.Name() != potNeigb.Name() && potNeigb.DistanceTo(point) <= epsilon {
			neighbours = append(neighbours, potNeigb)
		}
	}
	return neighbours
}

// Try to expand existing clutser
func expandCluster[T Point](cluster, neighbours []T, visited map[string]bool, minDensity int, eps float64) []T {
	seed := make([]T, len(neighbours))
	copy(seed, neighbours)

	// Create a new set for merging
	set := make(map[string]T, len(cluster)+len(neighbours))
	merge(set, cluster...)

	// Merge all the points
	for _, point := range seed {
		clustered, isVisited := visited[point.Name()]
		if !isVisited {
			currentNeighbours := findNeighbours(point, seed, eps)
			if len(currentNeighbours)+1 >= minDensity {
				visited[point.Name()] = true
				merge(set, currentNeighbours...)
			}
		}

		if isVisited && !clustered {
			visited[point.Name()] = true
			merge(set, point)
		}
	}

	// Flatten and return the cluster
	merged := make([]T, 0, len(set))
	for _, v := range set {
		merged = append(merged, v)
	}
	return merged
}

func merge[T Point](dst map[string]T, src ...T) {
	for _, v := range src {
		dst[v.Name()] = v
	}
}
