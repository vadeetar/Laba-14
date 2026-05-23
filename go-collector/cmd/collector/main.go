package main

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/nats-io/nats.go"
	clientv3 "go.etcd.io/etcd/client/v3"
)

type League struct {
	ID    string `json:"id"`
	Name  string `json:"name"`
	Sport string `json:"sport"`
}

type Config struct {
	Leagues []League `json:"leagues"`
}

type MatchEvent struct {
	EventID    string    `json:"event_id"`
	LeagueID   string    `json:"league_id"`
	LeagueName string    `json:"league_name"`
	Sport      string    `json:"sport"`
	HomeTeam   string    `json:"home_team"`
	AwayTeam   string    `json:"away_team"`
	HomeScore  int       `json:"home_score"`
	AwayScore  int       `json:"away_score"`
	TotalGoals int       `json:"total_goals"`
	EventDate  string    `json:"event_date"`
	Status     string    `json:"status"`
	Collected  time.Time `json:"collected_at"`
	WorkerID   string    `json:"worker_id"`
	Source     string    `json:"source"`
}

type WindowAggregate struct {
	WindowStart time.Time `json:"window_start"`
	WindowEnd   time.Time `json:"window_end"`
	LeagueID    string    `json:"league_id"`
	LeagueName  string    `json:"league_name"`
	Sport       string    `json:"sport"`
	MatchCount  int       `json:"match_count"`
	AvgGoals    float64   `json:"avg_goals"`
	MinGoals    int       `json:"min_goals"`
	MaxGoals    int       `json:"max_goals"`
	SumGoals    int       `json:"sum_goals"`
	WorkerID    string    `json:"worker_id"`
}

type Collector struct {
	cfg          Config
	workerID     string
	outputDir    string
	natsURL      string
	etcdEndpoint string
	interval     time.Duration
	batchSize    int
	batchFlush   time.Duration
	windowSize   time.Duration

	httpClient *http.Client
	eventsCh   chan MatchEvent
	batchCh    chan []MatchEvent
	windowCh   chan WindowAggregate
	nc         *nats.Conn
	etcd       *clientv3.Client

	mu       sync.Mutex
	buffer   []MatchEvent
	recent   []MatchEvent
	lastSave time.Time
	windows  map[string][]MatchEvent
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func getEnvDuration(key, fallback string) time.Duration {
	d, err := time.ParseDuration(getEnv(key, fallback))
	if err != nil {
		d, _ = time.ParseDuration(fallback)
	}
	return d
}

func getEnvInt(name string, fallback int) int {
	v := getEnv(name, "")
	if v == "" {
		return fallback
	}
	n, err := strconv.Atoi(v)
	if err != nil {
		return fallback
	}
	return n
}

func loadConfig(path string) (Config, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return Config{}, err
	}
	var cfg Config
	if err := json.Unmarshal(data, &cfg); err != nil {
		return Config{}, err
	}
	return cfg, nil
}

func parseScore(raw string) int {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return 0
	}
	n, err := strconv.Atoi(raw)
	if err != nil {
		return 0
	}
	return n
}

func (c *Collector) fetchLeagueEvents(ctx context.Context, league League) ([]MatchEvent, error) {
	endpoints := []string{
		fmt.Sprintf("https://www.thesportsdb.com/api/v1/json/3/eventspastleague.php?id=%s", league.ID),
		fmt.Sprintf("https://www.thesportsdb.com/api/v1/json/3/eventsnextleague.php?id=%s", league.ID),
	}

	now := time.Now().UTC()
	events := make([]MatchEvent, 0)

	for _, url := range endpoints {
		req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
		if err != nil {
			return nil, err
		}

		resp, err := c.httpClient.Do(req)
		if err != nil {
			return nil, err
		}

		body, err := io.ReadAll(resp.Body)
		resp.Body.Close()
		if err != nil {
			return nil, err
		}

		var payload struct {
			Events []map[string]any `json:"events"`
		}
		if err := json.Unmarshal(body, &payload); err != nil {
			return nil, err
		}
		if payload.Events == nil {
			continue
		}

		for _, item := range payload.Events {
			homeScore := parseScore(fmt.Sprint(item["intHomeScore"]))
			awayScore := parseScore(fmt.Sprint(item["intAwayScore"]))
			event := MatchEvent{
				EventID:    fmt.Sprint(item["idEvent"]),
				LeagueID:   league.ID,
				LeagueName: league.Name,
				Sport:      league.Sport,
				HomeTeam:   fmt.Sprint(item["strHomeTeam"]),
				AwayTeam:   fmt.Sprint(item["strAwayTeam"]),
				HomeScore:  homeScore,
				AwayScore:  awayScore,
				TotalGoals: homeScore + awayScore,
				EventDate:  fmt.Sprint(item["dateEvent"]),
				Status:     fmt.Sprint(item["strStatus"]),
				Collected:  now,
				WorkerID:   c.workerID,
				Source:     "thesportsdb",
			}
			if event.EventID == "" || event.HomeTeam == "" || event.AwayTeam == "" {
				continue
			}
			events = append(events, event)
		}
	}
	return events, nil
}

func (c *Collector) registerWorker(ctx context.Context) error {
	if c.etcd == nil {
		return nil
	}
	key := fmt.Sprintf("/lab14/workers/%s", c.workerID)
	_, err := c.etcd.Put(ctx, key, time.Now().UTC().Format(time.RFC3339))
	return err
}

func (c *Collector) assignedLeagues(ctx context.Context) []League {
	if c.etcd == nil || len(c.cfg.Leagues) == 0 {
		return c.cfg.Leagues
	}

	resp, err := c.etcd.Get(ctx, "/lab14/workers/", clientv3.WithPrefix())
	if err != nil || len(resp.Kvs) == 0 {
		return c.cfg.Leagues
	}

	workers := make([]string, 0, len(resp.Kvs))
	for _, kv := range resp.Kvs {
		parts := strings.Split(string(kv.Key), "/")
		workers = append(workers, parts[len(parts)-1])
	}

	myIndex := 0
	for i, w := range workers {
		if w == c.workerID {
			myIndex = i
			break
		}
	}

	sharded := make([]League, 0)
	for i, league := range c.cfg.Leagues {
		if i%len(workers) == myIndex {
			sharded = append(sharded, league)
		}
	}
	if len(sharded) == 0 {
		return c.cfg.Leagues[:1]
	}
	names := make([]string, len(sharded))
	for i, l := range sharded {
		names[i] = l.Name
	}
	log.Printf("etcd sharding: worker=%s total_workers=%d assigned=%v", c.workerID, len(workers), names)
	return sharded
}

func (c *Collector) collectOnce(ctx context.Context) {
	leagues := c.assignedLeagues(ctx)
	var wg sync.WaitGroup
	results := make(chan []MatchEvent, len(leagues))

	for _, league := range leagues {
		wg.Add(1)
		go func(l League) {
			defer wg.Done()
			events, err := c.fetchLeagueEvents(ctx, l)
			if err != nil {
				log.Printf("fetch league %s failed: %v", l.ID, err)
				return
			}
			results <- events
		}(league)
	}

	go func() {
		wg.Wait()
		close(results)
	}()

	total := 0
	for batch := range results {
		total += len(batch)
		for _, event := range batch {
			c.eventsCh <- event
		}
	}
	log.Printf("collected %d events from %d leagues", total, len(leagues))
}

func (c *Collector) runBatcher(ctx context.Context) {
	ticker := time.NewTicker(c.batchFlush)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			c.flushBuffer(true)
			return
		case event := <-c.eventsCh:
			c.mu.Lock()
			c.buffer = append(c.buffer, event)
			shouldFlush := len(c.buffer) >= c.batchSize
			c.mu.Unlock()
			if shouldFlush {
				c.flushBuffer(false)
			}
		case <-ticker.C:
			c.flushBuffer(false)
		}
	}
}

func (c *Collector) flushBuffer(force bool) {
	c.mu.Lock()
	if len(c.buffer) == 0 {
		c.mu.Unlock()
		return
	}
	if !force && len(c.buffer) < c.batchSize && time.Since(c.lastSave) < c.batchFlush {
		c.mu.Unlock()
		return
	}
	batch := make([]MatchEvent, len(c.buffer))
	copy(batch, c.buffer)
	c.buffer = c.buffer[:0]
	c.lastSave = time.Now().UTC()
	c.mu.Unlock()

	c.batchCh <- batch
}

func (c *Collector) storeRecent(batch []MatchEvent) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.recent = append(c.recent, batch...)
	if len(c.recent) > 1000 {
		c.recent = c.recent[len(c.recent)-1000:]
	}
}

func (c *Collector) snapshotRecent() []MatchEvent {
	c.mu.Lock()
	defer c.mu.Unlock()
	out := make([]MatchEvent, len(c.recent))
	copy(out, c.recent)
	return out
}

func (c *Collector) writeBatch(batch []MatchEvent) error {
	if len(batch) == 0 {
		return nil
	}

	if err := os.MkdirAll(c.outputDir, 0o755); err != nil {
		return err
	}

	filename := filepath.Join(c.outputDir, fmt.Sprintf("matches_%s.jsonl", time.Now().UTC().Format("20060102_150405")))
	file, err := os.OpenFile(filename, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0o644)
	if err != nil {
		return err
	}
	defer file.Close()

	writer := bufio.NewWriter(file)
	for _, event := range batch {
		line, err := json.Marshal(event)
		if err != nil {
			return err
		}
		if _, err := writer.Write(append(line, '\n')); err != nil {
			return err
		}
	}
	if err := writer.Flush(); err != nil {
		return err
	}

	if c.nc != nil {
		for _, event := range batch {
			payload, _ := json.Marshal(event)
			if err := c.nc.Publish("sports.matches", payload); err != nil {
				log.Printf("nats publish failed: %v", err)
			}
		}
	}

	c.storeRecent(batch)

	if err := c.exportMatchesArrow(batch); err != nil {
		log.Printf("arrow export failed: %v", err)
	}

	c.mu.Lock()
	for _, event := range batch {
		key := event.LeagueID
		c.windows[key] = append(c.windows[key], event)
	}
	c.mu.Unlock()

	log.Printf("saved batch of %d events to %s", len(batch), filename)
	return nil
}

func (c *Collector) runWriter(ctx context.Context) {
	for {
		select {
		case <-ctx.Done():
			return
		case batch := <-c.batchCh:
			if err := c.writeBatch(batch); err != nil {
				log.Printf("write batch failed: %v", err)
			}
		}
	}
}

func aggregateWindow(leagueID string, events []MatchEvent, start, end time.Time, workerID string) WindowAggregate {
	if len(events) == 0 {
		return WindowAggregate{}
	}

	sum := 0
	minGoals := events[0].TotalGoals
	maxGoals := events[0].TotalGoals
	for _, e := range events {
		sum += e.TotalGoals
		if e.TotalGoals < minGoals {
			minGoals = e.TotalGoals
		}
		if e.TotalGoals > maxGoals {
			maxGoals = e.TotalGoals
		}
	}

	return WindowAggregate{
		WindowStart: start,
		WindowEnd:   end,
		LeagueID:    leagueID,
		LeagueName:  events[0].LeagueName,
		Sport:       events[0].Sport,
		MatchCount:  len(events),
		AvgGoals:    float64(sum) / float64(len(events)),
		MinGoals:    minGoals,
		MaxGoals:    maxGoals,
		SumGoals:    sum,
		WorkerID:    workerID,
	}
}

func (c *Collector) runWindowAggregator(ctx context.Context) {
	ticker := time.NewTicker(c.windowSize)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			c.emitWindows(true)
			return
		case <-ticker.C:
			c.emitWindows(false)
		}
	}
}

func (c *Collector) emitWindows(final bool) {
	c.mu.Lock()
	defer c.mu.Unlock()

	now := time.Now().UTC()
	start := now.Add(-c.windowSize)

	for leagueID, events := range c.windows {
		if len(events) == 0 {
			continue
		}
		agg := aggregateWindow(leagueID, events, start, now, c.workerID)
		c.windowCh <- agg
		if final {
			delete(c.windows, leagueID)
		} else {
			c.windows[leagueID] = nil
		}
	}
}

func (c *Collector) runWindowWriter(ctx context.Context) {
	for {
		select {
		case <-ctx.Done():
			return
		case agg := <-c.windowCh:
			if agg.MatchCount == 0 {
				continue
			}
	if err := c.saveWindowAggregate(agg); err != nil {
				log.Printf("save window failed: %v", err)
			}
			if err := c.exportWindowsArrow(agg); err != nil {
				log.Printf("arrow window export failed: %v", err)
			}
		}
	}
}

func (c *Collector) saveWindowAggregate(agg WindowAggregate) error {
	if err := os.MkdirAll(c.outputDir, 0o755); err != nil {
		return err
	}

	path := filepath.Join(c.outputDir, "window_aggregates.jsonl")
	file, err := os.OpenFile(path, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0o644)
	if err != nil {
		return err
	}
	defer file.Close()

	line, err := json.Marshal(agg)
	if err != nil {
		return err
	}
	if _, err := file.Write(append(line, '\n')); err != nil {
		return err
	}

	if c.nc != nil {
		payload, _ := json.Marshal(agg)
		_ = c.nc.Publish("sports.windows", payload)
	}
	return nil
}

func (c *Collector) runCollectorLoop(ctx context.Context) {
	ticker := time.NewTicker(c.interval)
	defer ticker.Stop()

	c.collectOnce(ctx)
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			c.collectOnce(ctx)
		}
	}
}

func (c *Collector) connectNATS() error {
	if c.natsURL == "" {
		return nil
	}
	nc, err := nats.Connect(c.natsURL, nats.MaxReconnects(10))
	if err != nil {
		return err
	}
	c.nc = nc
	log.Printf("connected to NATS at %s", c.natsURL)
	return nil
}

func (c *Collector) connectEtcd(ctx context.Context) error {
	if c.etcdEndpoint == "" {
		return nil
	}
	cli, err := clientv3.New(clientv3.Config{
		Endpoints:   []string{c.etcdEndpoint},
		DialTimeout: 5 * time.Second,
	})
	if err != nil {
		return err
	}
	c.etcd = cli
	if err := c.registerWorker(ctx); err != nil {
		log.Printf("etcd register failed: %v", err)
	}
	log.Printf("connected to etcd at %s", c.etcdEndpoint)
	return nil
}

func (c *Collector) close() {
	if c.nc != nil {
		c.nc.Drain()
	}
	if c.etcd != nil {
		_ = c.etcd.Close()
	}
}

func main() {
	log.SetFlags(log.LstdFlags | log.Lmicroseconds)

	cfgPath := getEnv("CONFIG_PATH", "config/leagues.json")
	cfg, err := loadConfig(cfgPath)
	if err != nil {
		log.Fatalf("load config: %v", err)
	}

	collector := &Collector{
		cfg:          cfg,
		workerID:     getEnv("WORKER_ID", "worker-1"),
		outputDir:    getEnv("OUTPUT_DIR", "data"),
		natsURL:      getEnv("NATS_URL", ""),
		etcdEndpoint: getEnv("ETCD_ENDPOINTS", ""),
		interval:     getEnvDuration("COLLECT_INTERVAL", "30s"),
		batchSize:    getEnvInt("BATCH_SIZE", 15),
		batchFlush:   getEnvDuration("BATCH_FLUSH", "5s"),
		windowSize:   getEnvDuration("WINDOW_SIZE", "60s"),
		httpClient:   &http.Client{Timeout: 20 * time.Second},
		eventsCh:     make(chan MatchEvent, 256),
		batchCh:      make(chan []MatchEvent, 32),
		windowCh:     make(chan WindowAggregate, 32),
		windows:      make(map[string][]MatchEvent),
		lastSave:     time.Now().UTC(),
	}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	if err := collector.connectNATS(); err != nil {
		log.Printf("nats unavailable: %v", err)
	}
	if err := collector.connectEtcd(ctx); err != nil {
		log.Printf("etcd unavailable: %v", err)
	}
	defer collector.close()

	if getEnv("BENCHMARK_MODE", "") == "1" {
		runBenchmarkMode(collector)
		return
	}

	go collector.runBatcher(ctx)
	go collector.runWriter(ctx)
	go collector.runWindowAggregator(ctx)
	go collector.runWindowWriter(ctx)

	go collector.runCollectorLoop(ctx)

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	sig := <-sigCh
	log.Printf("received signal %s, shutting down gracefully...", sig)
	cancel()

	time.Sleep(2 * time.Second)
	collector.flushBuffer(true)
	log.Println("shutdown complete")
}
