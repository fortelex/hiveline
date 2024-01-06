package main

import (
	"context"
	"fmt"
	"github.com/Vector-Hector/fptf"
	"github.com/kyroy/kdtree"
	"github.com/paulmach/orb"
	"github.com/paulmach/orb/planar"
	"go.mongodb.org/mongo-driver/bson"
	"time"
)

type GraphNode struct {
	Id    uint32
	Point orb.Point
}

func (node *GraphNode) Name() string {
	return fmt.Sprintf("%d", node.Id)
}

func (node *GraphNode) DistanceTo(point Point) float64 {
	return planar.DistanceSquared(node.Point, point.(*GraphNode).Point)
}

func (node *GraphNode) Dimensions() int {
	return 2
}

func (node *GraphNode) Dimension(i int) float64 {
	return node.Point[i]
}

type ArcVisitor struct {
	VcId          string `json:"vcId" bson:"vcId"`
	RouteOptionId string `json:"routeOptionId" bson:"routeOptionId"`
}

type Arc []ArcVisitor

type Graph struct {
	Nodes []orb.Point
	Edges []map[uint32]Arc
	Mode  fptf.Mode
}

func getGraph(options []*RouteOption, mode fptf.Mode) *Graph {
	t := time.Now()

	traces := reduceTraces(options, mode)

	fmt.Println("reduced traces in", time.Since(t))
	t = time.Now()

	fmt.Println("clustering", len(traces.Nodes), "nodes")

	clusters := ClusterWithTree(2, 0.00001, 50, traces.Tree, traces.Nodes...)

	fmt.Println("clustered in", time.Since(t))
	t = time.Now()

	nodes := make([]orb.Point, len(clusters))

	for i, cluster := range clusters {
		var sumX, sumY float64
		for _, node := range cluster {
			sumX += node.Point[0]
			sumY += node.Point[1]
		}
		nodes[i] = orb.Point{sumX / float64(len(cluster)), sumY / float64(len(cluster))}
	}

	revKeys := make(map[uint32]int, len(traces.Nodes))
	for i, cluster := range clusters {
		for _, node := range cluster {
			revKeys[node.Id] = i
		}
	}

	// add all nodes that are not in a cluster
	for i, node := range traces.Nodes {
		_, ok := revKeys[uint32(i)]
		if ok {
			continue
		}

		revKeys[uint32(i)] = len(nodes)
		nodes = append(nodes, node.Point)
	}

	fmt.Println("calculated centroids in", time.Since(t))
	t = time.Now()

	edges := make([]map[uint32]Arc, len(nodes))

	for _, trace := range traces.Traces {
		for i, from := range trace[:len(trace)-1] {
			to := trace[i+1]

			fromCluster := revKeys[uint32(from)]
			toCluster := revKeys[uint32(to)]

			if fromCluster == toCluster {
				continue
			}

			if fromCluster > toCluster {
				fromCluster, toCluster = toCluster, fromCluster
			}

			if edges[fromCluster] == nil {
				edges[fromCluster] = make(map[uint32]Arc)
			}

			if edges[fromCluster][uint32(toCluster)] == nil {
				edges[fromCluster][uint32(toCluster)] = make(Arc, 0)
			}

			edges[fromCluster][uint32(toCluster)] = append(edges[fromCluster][uint32(toCluster)], ArcVisitor{})
		}
	}

	fmt.Println("calculated edges in", time.Since(t))
	t = time.Now()

	return &Graph{
		Nodes: nodes,
		Edges: edges,
		Mode:  mode,
	}
}

type ReducedTracesRepresentation struct {
	Tree   *kdtree.KDTree
	Nodes  []*GraphNode
	Traces [][]int
}

func reduceTraces(options []*RouteOption, mode fptf.Mode) *ReducedTracesRepresentation {
	nodeTree := kdtree.New([]kdtree.Point{})
	lastPointId := uint32(0)
	nodes := make([]*GraphNode, 0)
	traces := make([][]int, 0)

	for _, option := range options {
		mainTrace := extractTrace(option)

		split := splitTraceByMode(mainTrace, mode)

		for _, subTrace := range split {
			outTrace := make([]int, 0, len(subTrace.Trace))

			for _, elem := range subTrace.Trace {
				id, ok := getNodeId(nodeTree, &elem)
				if !ok {
					id = lastPointId
					lastPointId++
					node := &GraphNode{
						Id:    id,
						Point: elem.Point,
					}
					nodeTree.Insert(node)
					nodes = append(nodes, node)
				}

				outTrace = append(outTrace, int(id))
			}

			traces = append(traces, outTrace)
		}
	}

	return &ReducedTracesRepresentation{
		Tree:   nodeTree,
		Nodes:  nodes,
		Traces: traces,
	}
}

func getNodeId(nodeTree *kdtree.KDTree, elem *TraceElement) (uint32, bool) {
	const epsilon = 0.0001

	nearest := nodeTree.KNN(&GraphNode{
		Point: elem.Point,
	}, 1)

	if len(nearest) == 0 {
		return 0, false
	}

	nearestNode := nearest[0].(*GraphNode)

	if planar.DistanceSquared(elem.Point, nearestNode.Point) > epsilon*epsilon {
		return 0, false
	}

	return nearest[0].(*GraphNode).Id, true
}

type MongoGraph struct {
	SimId string      `json:"simId" bson:"simId"`
	Mode  fptf.Mode   `json:"mode" bson:"mode"`
	Nodes []orb.Point `json:"nodes" bson:"nodes"`
	Edges [][2]uint32 `json:"edges" bson:"edges"`
}

type MongoArc struct {
	SimId    string       `json:"simId" bson:"simId"`
	Mode     fptf.Mode    `json:"mode" bson:"mode"`
	From     uint32       `json:"from" bson:"from"`
	To       uint32       `json:"to" bson:"to"`
	Visitors []ArcVisitor `json:"visitors" bson:"visitors"`
}

func saveToMongo(simId string, graph *Graph) {
	flattenedArcs := make([][2]uint32, 0)

	const visitorThreshold = 0

	for from, arc := range graph.Edges {
		for to, visitors := range arc {
			if len(visitors) < visitorThreshold {
				continue
			}

			flattenedArcs = append(flattenedArcs, [2]uint32{uint32(from), to})
		}
	}

	mongoGraph := &MongoGraph{
		SimId: simId,
		Mode:  graph.Mode,
		Nodes: graph.Nodes,
		Edges: flattenedArcs,
	}

	mongoArcs := make([]interface{}, 0)

	for from, arc := range graph.Edges {
		for to, visitors := range arc {
			if len(visitors) < visitorThreshold {
				continue
			}

			mongoArcs = append(mongoArcs, MongoArc{
				SimId:    simId,
				Mode:     graph.Mode,
				From:     uint32(from),
				To:       to,
				Visitors: visitors,
			})
		}
	}

	client, database := getDatabase()

	defer func() {
		if err := client.Disconnect(context.Background()); err != nil {
			panic(err)
		}
	}()

	db := client.Database(database)

	// delete any existing graph
	_, err := db.Collection("trace-graphs").DeleteMany(context.Background(), bson.M{
		"simId": simId,
		"mode":  graph.Mode,
	})
	if err != nil {
		panic(err)
	}

	_, err = db.Collection("trace-arcs").DeleteMany(context.Background(), bson.M{
		"simId": simId,
		"mode":  graph.Mode,
	})
	if err != nil {
		panic(err)
	}

	_, err = db.Collection("trace-graphs").InsertOne(context.Background(), mongoGraph)
	if err != nil {
		panic(err)
	}

	_, err = db.Collection("trace-arcs").InsertMany(context.Background(), mongoArcs)
	if err != nil {
		panic(err)
	}

}
