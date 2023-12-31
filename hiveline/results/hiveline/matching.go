package main

import (
	"fmt"
	"github.com/RyanCarrier/dijkstra"
	"github.com/kyroy/kdtree"
	"github.com/paulmach/orb"
	"github.com/paulmach/orb/planar"
	gml "github.com/yaricom/goGraphML/graphml"
	"math"
	"os"
	"strconv"
	"strings"
)

const noNode = uint32(math.MaxUint32)

func matchTraces(traces []Trace, streetGraph *StreetGraph, threadCount int) [][]*StreetGraphNode {
	outTraces := make([][]*StreetGraphNode, len(traces))

	done := make(chan bool, threadCount)

	for i := 0; i < threadCount; i++ {
		go func(i int) {
			for j := i; j < len(traces); j += threadCount {
				if j%100 == 0 {
					fmt.Println("matching trace", j, "of", len(traces))
				}

				matchedTrace := getNodeOptionTrace(traces[j], streetGraph) //matchTraceConnected(traces[j], streetGraph, i)

				outTrace := make([]*StreetGraphNode, len(matchedTrace))
				for i, node := range matchedTrace {
					outTrace[i] = streetGraph.Nodes[node]
				}

				outTraces[j] = outTrace
			}
			done <- true
		}(i)
	}

	for i := 0; i < threadCount; i++ {
		<-done
	}

	return outTraces
}

func matchTraceConnected(trace Trace, streetGraph *StreetGraph, dGraphKey int) []uint32 {
	nodeOptionTrace := getNodeOptionTrace(trace, streetGraph)

	return matchTrace(nodeOptionTrace, streetGraph, dGraphKey)
}

func matchTrace(nodeOptionTrace []uint32, streetGraph *StreetGraph, dGraphKey int) []uint32 {
	matchedTrace := make([]uint32, 0)

	lastNode := noNode

	dGraph := streetGraph.Graphs[dGraphKey]

	for _, node := range nodeOptionTrace {
		if node == noNode {
			continue
		}

		if lastNode == noNode {
			lastNode = node
			continue
		}

		bestPath, err := dGraph.Shortest(int(lastNode), int(node))
		var path []int

		if err != nil {
			path = []int{int(lastNode), int(node)}
		} else {
			path = bestPath.Path
		}

		if len(matchedTrace) > 0 {
			path = path[1:] // remove first element (already matched)
		}

		for _, pathNode := range path {
			matchedTrace = append(matchedTrace, uint32(pathNode))
		}
	}

	return matchedTrace
}

func getNodeOptionTrace(trace Trace, streetGraph *StreetGraph) []uint32 {
	nodeOptionTrace := make([]uint32, len(trace.Trace))

	for i, elem := range trace.Trace {
		matchedElement := streetGraph.NodeTree.KNN(&elem, 1)

		if len(matchedElement) == 0 {
			nodeOptionTrace[i] = noNode
			continue
		}

		node, ok := matchedElement[0].(*StreetGraphNode)
		if ok {
			nodeOptionTrace[i] = node.Id
			continue
		}

		edgePointer, ok := matchedElement[0].(*StreetGraphEdgePointer)
		if ok {
			fromDist := planar.DistanceSquared(elem.Point, streetGraph.Nodes[edgePointer.From].Point)
			toDist := planar.DistanceSquared(elem.Point, streetGraph.Nodes[edgePointer.To].Point)
			if fromDist < toDist {
				nodeOptionTrace[i] = edgePointer.From
			} else {
				nodeOptionTrace[i] = edgePointer.To
			}
			continue
		}

		panic("unknown element type")
	}

	return nodeOptionTrace
}

type StreetGraphNode struct {
	Id        uint32
	OsmNodeId uint64
	Point     orb.Point
}

func (g *StreetGraphNode) Dimensions() int {
	return 2
}

func (g *StreetGraphNode) Dimension(i int) float64 {
	return g.Point[i]
}

type StreetGraphEdgePointer struct {
	From  uint32
	To    uint32
	Point orb.Point
}

func (g *StreetGraphEdgePointer) Dimensions() int {
	return 2
}

func (g *StreetGraphEdgePointer) Dimension(i int) float64 {
	return g.Point[i]
}

type StreetGraph struct {
	Nodes    []*StreetGraphNode
	NodeTree *kdtree.KDTree
	Graphs   []*dijkstra.Graph // list of identical graphs for multithreading
}

func getStreetGraph(dGraphCount int) *StreetGraph {
	// osmnx data keys:
	// d4: latitude
	// d5: longitude
	// d9: osm way id
	// d10: boolean is oneway (osm:oneway)
	// d11: number of lanes (osm:lanes)
	// d12: street name (osm:name)
	// d13: street type (osm:highway)
	// d14: street max speed (osm:maxspeed)
	// d15: unknown boolean flag
	// d16: length in meters
	// d17: LINESTRING for long ways

	path := "./cache/graphs/metropolitan-region-eindhoven-netherlands-2022-10-04-undirected.graphml"

	file, err := os.Open(path)
	if err != nil {
		panic(err)
	}

	defer file.Close()

	graphml := gml.NewGraphML("Eindhoven, Netherlands Street Graph")
	err = graphml.Decode(file)
	if err != nil {
		panic(err)
	}

	graph := graphml.Graphs[0]

	nodes := make([]*StreetGraphNode, len(graph.Nodes))
	nodeIdIndex := make(map[string]uint32)
	nextNodeId := uint32(0)
	dGraphs := make([]*dijkstra.Graph, dGraphCount)
	treePoints := make([]kdtree.Point, 0)

	for i := 0; i < dGraphCount; i++ {
		dGraphs[i] = dijkstra.NewGraph()
	}

	for i, node := range graph.Nodes {
		nodeId, err := strconv.Atoi(node.ID)
		if err != nil {
			panic(err)
		}

		var lon, lat float64

		for _, data := range node.Data {
			if data.Key == "d4" {
				lat, err = strconv.ParseFloat(data.Value, 64)
				if err != nil {
					panic(err)
				}
			}

			if data.Key == "d5" {
				lon, err = strconv.ParseFloat(data.Value, 64)
				if err != nil {
					panic(err)
				}
			}
		}

		point := &StreetGraphNode{
			Id:        nextNodeId,
			OsmNodeId: uint64(nodeId),
			Point:     orb.Point{lon, lat},
		}
		nodes[i] = point
		nodeIdIndex[node.ID] = nextNodeId

		for _, dGraph := range dGraphs {
			dGraph.AddVertex(int(nextNodeId))
		}

		treePoints = append(treePoints, point)

		nextNodeId++
	}

	for _, edge := range graph.Edges {
		from, ok := nodeIdIndex[edge.Source]
		if !ok {
			panic("from not found")
		}

		to, ok := nodeIdIndex[edge.Target]
		if !ok {
			panic("to not found")
		}

		var dist float64
		var lineString string

		for _, data := range edge.Data {
			if data.Key == "d16" {
				dist, err = strconv.ParseFloat(data.Value, 64)
				if err != nil {
					panic(err)
				}
			}

			if data.Key == "d17" {
				lineString = data.Value
			}
		}

		for _, dGraph := range dGraphs {
			err := dGraph.AddArc(int(from), int(to), int64(dist*100))
			if err != nil {
				panic(err)
			}

			err = dGraph.AddArc(int(to), int(from), int64(dist*100))
			if err != nil {
				panic(err)
			}
		}

		line := []orb.Point{nodes[from].Point, nodes[to].Point}

		if lineString != "" {
			subLine, err := parseLineString(lineString)
			if err != nil {
				panic(err)
			}

			line = append(append([]orb.Point{nodes[from].Point}, subLine...), nodes[to].Point)
		}

		pointers := getPointers(line, from, to)

		for _, pointer := range pointers {
			treePoints = append(treePoints, pointer)
		}
	}

	fmt.Println("building tree")
	fmt.Println(len(treePoints))

	tree := kdtree.New(treePoints)

	return &StreetGraph{
		Nodes:    nodes,
		NodeTree: tree,
		Graphs:   dGraphs,
	}
}

func getPointers(line []orb.Point, from, to uint32) []*StreetGraphEdgePointer {
	pointers := make([]*StreetGraphEdgePointer, 0)

	const maxPointDist = 0.0005

	for i := 0; i < len(line); i++ {
		if i != 0 {
			dist := planar.Distance(line[i-1], line[i])

			if dist > maxPointDist {
				steps := int(dist / maxPointDist)
				for j := 1; j < steps; j++ {
					t := float64(j) / float64(steps)
					point := orb.Point{
						line[i-1][0] + (line[i][0]-line[i-1][0])*t,
						line[i-1][1] + (line[i][1]-line[i-1][1])*t,
					}
					pointers = append(pointers, &StreetGraphEdgePointer{
						From:  from,
						To:    to,
						Point: point,
					})
				}
			}
		}

		pointers = append(pointers, &StreetGraphEdgePointer{
			From:  from,
			To:    to,
			Point: line[i],
		})
	}

	return pointers
}

func parseLineString(input string) ([]orb.Point, error) {
	var lineString []orb.Point
	input = strings.TrimPrefix(input, "LINESTRING ")
	input = strings.Trim(input, "()")

	coordinateStrings := strings.Split(input, ", ")

	for _, coordStr := range coordinateStrings {
		coords := strings.Split(coordStr, " ")

		if len(coords) != 2 {
			return nil, fmt.Errorf("invalid coordinate pair: %s", coordStr)
		}

		lon, err := strconv.ParseFloat(coords[0], 64)
		if err != nil {
			return nil, fmt.Errorf("invalid longitude: %s", coords[1])
		}

		lat, err := strconv.ParseFloat(coords[1], 64)
		if err != nil {
			return nil, fmt.Errorf("invalid latitude: %s", coords[0])
		}

		lineString = append(lineString, orb.Point{lon, lat})
	}

	return lineString, nil
}
