package main

import (
	"fmt"
	"github.com/paulmach/orb"
)

type vertexFlow struct {
	isRelevant bool // do one pair of edge visitor sets not match
	visitorSet map[ArcVisitor]bool
	edges      []uint32
}

func DecimateByIrrelevantArcs(graph *Graph) *Graph {
	vertexFlows := make([]*vertexFlow, len(graph.Nodes))

	for i := range vertexFlows {
		vertexFlows[i] = &vertexFlow{
			isRelevant: true,
			edges:      []uint32{},
		}
	}

	for i, edges := range graph.Edges {
		for j, arcs := range edges {
			if len(arcs) == 0 {
				continue
			}

			flow := make(map[ArcVisitor]bool)

			for _, visitor := range arcs {
				flow[visitor] = true
			}

			vertexFlows[i].edges = append(vertexFlows[i].edges, j)
			vertexFlows[j].edges = append(vertexFlows[j].edges, uint32(i))

			if vertexFlows[i].visitorSet != nil && visitorSetEqual(vertexFlows[i].visitorSet, flow) {
				vertexFlows[i].isRelevant = false
			}

			if vertexFlows[j].visitorSet != nil && visitorSetEqual(vertexFlows[j].visitorSet, flow) {
				vertexFlows[j].isRelevant = false
			}

			vertexFlows[i].visitorSet = flow
			vertexFlows[j].visitorSet = flow
		}
	}

	newNodes := make([]orb.Point, 0, len(graph.Nodes))
	newEdges := make([]map[uint32]Arc, 0, len(graph.Nodes))
	remap := make(map[uint32]uint32, len(graph.Nodes))

	for i, flow := range vertexFlows {
		if flow.isRelevant || flow.edges != 2 {
			remap[uint32(i)] = uint32(len(newNodes))
			newNodes = append(newNodes, graph.Nodes[i])
		}
	}

}

func visitorSetEqual(a, b map[ArcVisitor]bool) bool {
	if len(a) != len(b) {
		return false
	}

	for visitor := range a {
		if !b[visitor] {
			return false
		}
	}

	return true
}

func DecimateByCluster(graph *Graph, epsilon float64, k int) *Graph {
	nodes := make([]*GraphNode, len(graph.Nodes))

	for i, node := range graph.Nodes {
		nodes[i] = &GraphNode{
			Id:    uint32(i),
			Point: node,
		}
	}

	clusters := Cluster(2, epsilon, k, nodes...)

	newNodes := make([]orb.Point, len(clusters))

	for i, cluster := range clusters {
		sumX := 0.0
		sumY := 0.0

		for _, node := range cluster {
			sumX += node.Point[0]
			sumY += node.Point[1]
		}

		newNodes[i] = orb.Point{sumX / float64(len(cluster)), sumY / float64(len(cluster))}
	}

	revKeys := make(map[uint32]int, len(graph.Nodes))

	for i, cluster := range clusters {
		for _, node := range cluster {
			revKeys[node.Id] = i
		}
	}

	// add all nodes that are not in a cluster
	for i, node := range nodes {
		_, ok := revKeys[uint32(i)]
		if ok {
			continue
		}

		revKeys[uint32(i)] = len(newNodes)
		newNodes = append(newNodes, node.Point)
	}

	fmt.Println("got", len(newNodes), "nodes")

	edges := make([]map[uint32]Arc, len(newNodes))

	arcCount := 0

	for from, fromEdges := range graph.Edges {
		for to := range fromEdges {
			fromCluster := revKeys[uint32(from)]
			toCluster := revKeys[to]

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
			arcCount++
		}
	}

	fmt.Println("got", arcCount, "arcs")

	return &Graph{
		Nodes: newNodes,
		Edges: edges,
		Mode:  graph.Mode,
	}
}
