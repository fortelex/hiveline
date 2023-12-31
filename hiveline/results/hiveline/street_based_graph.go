package main

import (
	"fmt"
	"github.com/Vector-Hector/fptf"
	"github.com/paulmach/orb"
	"time"
)

func getStreetBasedGraph(options []*RouteOption, mode fptf.Mode) *Graph {
	t := time.Now()

	traces := getTraces(options)

	fmt.Println("got", len(traces), "traces in", time.Since(t))
	t = time.Now()

	traces = splitTracesByMode(traces, mode)

	fmt.Println("split traces by mode in", time.Since(t))
	fmt.Println("got", len(traces), "traces in", time.Since(t))
	t = time.Now()

	const threadCount = 12

	streetGraph := getStreetGraph(threadCount)

	fmt.Println("got street graph in", time.Since(t))
	t = time.Now()

	matched := matchTraces(traces, streetGraph, threadCount)

	fmt.Println("matched traces in", time.Since(t))
	t = time.Now()

	occurringNodes := make(map[uint32]*StreetGraphNode)

	for _, trace := range matched {
		for _, node := range trace {
			occurringNodes[node.Id] = node
		}
	}

	nodes := make([]orb.Point, 0)
	revKeys := make(map[uint32]uint32)

	for _, node := range occurringNodes {
		newId := uint32(len(nodes))
		revKeys[node.Id] = newId
		nodes = append(nodes, node.Point)
	}

	edges := make([]map[uint32]Arc, len(nodes))

	for _, trace := range matched {
		for i, from := range trace[:len(trace)-1] {
			to := trace[i+1]

			fromNodeKey := revKeys[from.Id]
			toNodeKey := revKeys[to.Id]

			if fromNodeKey == toNodeKey {
				continue
			}

			if fromNodeKey > toNodeKey {
				fromNodeKey, toNodeKey = toNodeKey, fromNodeKey
			}

			if edges[fromNodeKey] == nil {
				edges[fromNodeKey] = make(map[uint32]Arc)
			}

			if edges[fromNodeKey][toNodeKey] == nil {
				edges[fromNodeKey][toNodeKey] = make(Arc, 0)
			}

			edges[fromNodeKey][toNodeKey] = append(edges[fromNodeKey][toNodeKey], ArcVisitor{})
		}
	}

	fmt.Println("calculated graph in", time.Since(t))

	return &Graph{
		Nodes: nodes,
		Edges: edges,
		Mode:  mode,
	}
}

func splitTracesByMode(traces []Trace, mode fptf.Mode) []Trace {
	outTraces := make([]Trace, 0)

	for _, trace := range traces {
		subTraces := splitTraceByMode(trace, mode)

		outTraces = append(outTraces, subTraces...)
	}

	return outTraces
}

func splitTraceByMode(trace Trace, mode fptf.Mode) []Trace {
	outTraces := make([]Trace, 0)

	outTrace := make([]TraceElement, 0)

	for _, elem := range trace.Trace {
		if elem.Mode != mode {
			if len(outTrace) > 0 {
				outTraces = append(outTraces, Trace{
					VcId:          trace.VcId,
					RouteOptionId: trace.RouteOptionId,
					Trace:         outTrace,
				})
				outTrace = make([]TraceElement, 0)
			}
			continue
		}

		outTrace = append(outTrace, elem)
	}

	if len(outTrace) > 0 {
		outTraces = append(outTraces, Trace{
			VcId:          trace.VcId,
			RouteOptionId: trace.RouteOptionId,
			Trace:         outTrace,
		})
	}

	return outTraces
}
