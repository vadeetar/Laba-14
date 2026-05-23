package main

import (
	"context"
	"encoding/json"
	"log"
	"os"
	"runtime"
	"sync"
	"time"
)

type benchmarkResult struct {
	Collector       string  `json:"collector"`
	EventsCollected int     `json:"events_collected"`
	ElapsedSeconds  float64 `json:"elapsed_seconds"`
	CPUSeconds      float64 `json:"cpu_seconds"`
	PeakMemoryMB    float64 `json:"peak_memory_mb"`
	EventsPerSecond float64 `json:"events_per_second"`
	WorkerID        string  `json:"worker_id"`
}

func (c *Collector) collectAllEvents(ctx context.Context) []MatchEvent {
	leagues := c.assignedLeagues(ctx)
	all := make([]MatchEvent, 0)
	var wg sync.WaitGroup
	var mu sync.Mutex

	for _, league := range leagues {
		wg.Add(1)
		go func(l League) {
			defer wg.Done()
			events, err := c.fetchLeagueEvents(ctx, l)
			if err != nil {
				log.Printf("fetch league %s failed: %v", l.ID, err)
				return
			}
			mu.Lock()
			all = append(all, events...)
			mu.Unlock()
		}(league)
	}
	wg.Wait()
	return all
}

func runBenchmarkMode(collector *Collector) {
	ctx := context.Background()
	cpuStart := cpuTimeSeconds()
	started := time.Now()
	events := collector.collectAllEvents(ctx)
	elapsed := time.Since(started).Seconds()
	cpuUsed := cpuTimeSeconds() - cpuStart

	var mem runtime.MemStats
	runtime.ReadMemStats(&mem)
	peakMB := float64(mem.Alloc) / (1024 * 1024)

	result := benchmarkResult{
		Collector:       "go_goroutines",
		EventsCollected: len(events),
		ElapsedSeconds:  elapsed,
		CPUSeconds:      cpuUsed,
		PeakMemoryMB:    peakMB,
		WorkerID:        collector.workerID,
	}
	if elapsed > 0 {
		result.EventsPerSecond = float64(len(events)) / elapsed
	}

	if err := os.MkdirAll(collector.outputDir, 0o755); err != nil {
		log.Fatalf("mkdir output: %v", err)
	}

	outPath := collector.outputDir + "/go_collector_benchmark.json"
	payload, _ := json.MarshalIndent(result, "", "  ")
	if err := os.WriteFile(outPath, payload, 0o644); err != nil {
		log.Fatalf("write benchmark: %v", err)
	}

	if len(events) > 0 {
		collector.storeRecent(events)
		if err := collector.exportMatchesArrow(events); err != nil {
			log.Printf("arrow export failed: %v", err)
		}
		_ = collector.writeBatch(events)
	}

	log.Printf("benchmark complete: events=%d elapsed=%.4fs", len(events), elapsed)
}
