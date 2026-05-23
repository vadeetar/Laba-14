package main

import (
	"os"

	"github.com/apache/arrow-go/v18/arrow"
	"github.com/apache/arrow-go/v18/arrow/array"
	"github.com/apache/arrow-go/v18/arrow/ipc"
	"github.com/apache/arrow-go/v18/arrow/memory"
)

func matchSchema() *arrow.Schema {
	return arrow.NewSchema([]arrow.Field{
		{Name: "event_id", Type: arrow.BinaryTypes.String},
		{Name: "league_id", Type: arrow.BinaryTypes.String},
		{Name: "league_name", Type: arrow.BinaryTypes.String},
		{Name: "sport", Type: arrow.BinaryTypes.String},
		{Name: "home_team", Type: arrow.BinaryTypes.String},
		{Name: "away_team", Type: arrow.BinaryTypes.String},
		{Name: "home_score", Type: arrow.PrimitiveTypes.Int32},
		{Name: "away_score", Type: arrow.PrimitiveTypes.Int32},
		{Name: "total_goals", Type: arrow.PrimitiveTypes.Int32},
		{Name: "event_date", Type: arrow.BinaryTypes.String},
	}, nil)
}

func buildMatchRecord(events []MatchEvent) (arrow.Record, error) {
	pool := memory.NewGoAllocator()
	schema := matchSchema()
	b := array.NewRecordBuilder(pool, schema)
	defer b.Release()

	for _, e := range events {
		b.Field(0).(*array.StringBuilder).Append(e.EventID)
		b.Field(1).(*array.StringBuilder).Append(e.LeagueID)
		b.Field(2).(*array.StringBuilder).Append(e.LeagueName)
		b.Field(3).(*array.StringBuilder).Append(e.Sport)
		b.Field(4).(*array.StringBuilder).Append(e.HomeTeam)
		b.Field(5).(*array.StringBuilder).Append(e.AwayTeam)
		b.Field(6).(*array.Int32Builder).Append(int32(e.HomeScore))
		b.Field(7).(*array.Int32Builder).Append(int32(e.AwayScore))
		b.Field(8).(*array.Int32Builder).Append(int32(e.TotalGoals))
		b.Field(9).(*array.StringBuilder).Append(e.EventDate)
	}
	return b.NewRecord(), nil
}

func writeArrowIPC(path string, record arrow.Record) error {
	file, err := os.Create(path)
	if err != nil {
		return err
	}
	defer file.Close()

	writer := ipc.NewWriter(file, ipc.WithSchema(record.Schema()))
	if err := writer.Write(record); err != nil {
		return err
	}
	return writer.Close()
}

func (c *Collector) exportMatchesArrow(events []MatchEvent) error {
	if len(events) == 0 {
		return nil
	}
	record, err := buildMatchRecord(events)
	if err != nil {
		return err
	}
	defer record.Release()

	path := c.outputDir + "/matches.arrow"
	return writeArrowIPC(path, record)
}

func (c *Collector) exportWindowsArrow(agg WindowAggregate) error {
	pool := memory.NewGoAllocator()
	schema := arrow.NewSchema([]arrow.Field{
		{Name: "league_id", Type: arrow.BinaryTypes.String},
		{Name: "league_name", Type: arrow.BinaryTypes.String},
		{Name: "sport", Type: arrow.BinaryTypes.String},
		{Name: "match_count", Type: arrow.PrimitiveTypes.Int32},
		{Name: "avg_goals", Type: arrow.PrimitiveTypes.Float64},
		{Name: "sum_goals", Type: arrow.PrimitiveTypes.Int32},
	}, nil)

	b := array.NewRecordBuilder(pool, schema)
	defer b.Release()
	b.Field(0).(*array.StringBuilder).Append(agg.LeagueID)
	b.Field(1).(*array.StringBuilder).Append(agg.LeagueName)
	b.Field(2).(*array.StringBuilder).Append(agg.Sport)
	b.Field(3).(*array.Int32Builder).Append(int32(agg.MatchCount))
	b.Field(4).(*array.Float64Builder).Append(agg.AvgGoals)
	b.Field(5).(*array.Int32Builder).Append(int32(agg.SumGoals))

	record := b.NewRecord()
	defer record.Release()
	return writeArrowIPC(c.outputDir+"/windows.arrow", record)
}
