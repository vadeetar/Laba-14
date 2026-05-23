package main

import (
	"context"
	"log"
	"net"
	"strconv"
	"time"

	"github.com/apache/arrow-go/v18/arrow"
	"github.com/apache/arrow-go/v18/arrow/array"
	"github.com/apache/arrow-go/v18/arrow/flight"
	"github.com/apache/arrow-go/v18/arrow/ipc"
	"github.com/apache/arrow-go/v18/arrow/memory"
)

type sportsFlightServer struct {
	collector *Collector
}

func (s *sportsFlightServer) getLatestBatchSchema() (*arrow.Schema, error) {
	fields := []arrow.Field{
		{Name: "window_start", Type: arrow.FixedWidthTypes.Timestamp_us, Nullable: false},
		{Name: "window_end", Type: arrow.FixedWidthTypes.Timestamp_us, Nullable: false},
		{Name: "league_id", Type: arrow.BinaryTypes.String, Nullable: false},
		{Name: "league_name", Type: arrow.BinaryTypes.String, Nullable: false},
		{Name: "sport", Type: arrow.BinaryTypes.String, Nullable: false},
		{Name: "match_count", Type: arrow.PrimitiveTypes.Int32, Nullable: false},
		{Name: "avg_goals", Type: arrow.PrimitiveTypes.Float64, Nullable: false},
		{Name: "min_goals", Type: arrow.PrimitiveTypes.Int32, Nullable: false},
		{Name: "max_goals", Type: arrow.PrimitiveTypes.Int32, Nullable: false},
		{Name: "sum_goals", Type: arrow.PrimitiveTypes.Int32, Nullable: false},
	}
	return arrow.NewSchema(fields, nil), nil
}

func (s *sportsFlightServer) buildRecord(aggregates []WindowAggregate) (arrow.Record, error) {
	pool := memory.NewGoAllocator()
	schema, err := s.getLatestBatchSchema()
	if err != nil {
		return nil, err
	}

	n := len(aggregates)
	b := array.NewRecordBuilder(pool, schema)
	defer b.Release()

	for _, agg := range aggregates {
		b.Field(0).(*array.TimestampBuilder).Append(arrow.Timestamp(agg.WindowStart.UnixMicro()))
		b.Field(1).(*array.TimestampBuilder).Append(arrow.Timestamp(agg.WindowEnd.UnixMicro()))
		b.Field(2).(*array.StringBuilder).Append(agg.LeagueID)
		b.Field(3).(*array.StringBuilder).Append(agg.LeagueName)
		b.Field(4).(*array.StringBuilder).Append(agg.Sport)
		b.Field(5).(*array.Int32Builder).Append(int32(agg.MatchCount))
		b.Field(6).(*array.Float64Builder).Append(agg.AvgGoals)
		b.Field(7).(*array.Int32Builder).Append(int32(agg.MinGoals))
		b.Field(8).(*array.Int32Builder).Append(int32(agg.MaxGoals))
		b.Field(9).(*array.Int32Builder).Append(int32(agg.SumGoals))
	}

	return b.NewRecord(), nil
}

func (s *sportsFlightServer) GetFlightInfo(_ context.Context, _ *flight.Criteria) (*flight.FlightInfo, error) {
	schema, err := s.getLatestBatchSchema()
	if err != nil {
		return nil, err
	}
	desc := flight.FlightDescriptor{Type: flight.DescriptorPATH, Path: []string{"sports_windows"}}
	endpoints := []flight.FlightEndpoint{{Ticket: &flight.Ticket{Ticket: "sports_windows"}}}
	return &flight.FlightInfo{
		Schema:           flight.SerializeSchema(schema, memory.NewGoAllocator()),
		FlightDescriptor: &desc,
		Endpoint:         endpoints,
	}, nil
}

func (s *sportsFlightServer) DoGet(_ *flight.Ticket, stream flight.FlightService_DoGetServer) error {
	s.collector.mu.Lock()
	aggregates := make([]WindowAggregate, 0)
	now := time.Now().UTC()
	start := now.Add(-s.collector.windowSize)
	for leagueID, events := range s.collector.windows {
		if len(events) == 0 {
			continue
		}
		aggregates = append(aggregates, aggregateWindow(leagueID, events, start, now, s.collector.workerID))
	}
	s.collector.mu.Unlock()

	record, err := s.buildRecord(aggregates)
	if err != nil {
		return err
	}
	defer record.Release()

	writer := flight.NewRecordWriter(stream, ipc.WithSchema(record.Schema()))
	if err := writer.Write(record); err != nil {
		return err
	}
	return writer.Close()
}

func (s *sportsFlightServer) ListFlights(_ context.Context, _ *flight.Criteria) (flight.FlightService_ListFlightsServer, error) {
	return nil, flight.ErrUnimplemented
}

func (s *sportsFlightServer) GetSchema(_ context.Context, _ *flight.FlightDescriptor) (*flight.SchemaResult, error) {
	schema, err := s.getLatestBatchSchema()
	if err != nil {
		return nil, err
	}
	return &flight.SchemaResult{Schema: flight.SerializeSchema(schema, memory.NewGoAllocator())}, nil
}

func (s *sportsFlightServer) DoPut(flight.FlightService_DoPutServer) error {
	return flight.ErrUnimplemented
}

func (s *sportsFlightServer) DoAction(*flight.Action, flight.FlightService_DoActionServer) error {
	return flight.ErrUnimplemented
}

func (s *sportsFlightServer) ListActions(context.Context, *flight.Empty) (*flight.ListActionsResult, error) {
	return &flight.ListActionsResult{}, nil
}

func (s *sportsFlightServer) DoExchange(flight.FlightService_DoExchangeServer) error {
	return flight.ErrUnimplemented
}

func startArrowFlightServer(ctx context.Context, collector *Collector) {
	addr := net.JoinHostPort("0.0.0.0", fmtInt(collector.arrowPort))
	server := flight.NewFlightServer()
	server.RegisterFlightService(&sportsFlightServer{collector: collector})

	go func() {
		<-ctx.Done()
		server.Shutdown()
	}()

	go func() {
		log.Printf("Arrow Flight server listening on %s", addr)
		if err := server.Init(addr); err != nil {
			log.Printf("arrow flight init failed: %v", err)
		}
	}()
}

func fmtInt(v int) string {
	return strconv.Itoa(v)
}
