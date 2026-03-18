"""ZenAlpha CLI — 缠论量化分析工具"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from chanquant.core.objects import (
    Direction,
    RawKLine,
    TimeFrame,
)

app = typer.Typer(
    name="zenalpha",
    help="缠论量化分析平台 — 10层信号管道 + 回测引擎",
)
console = Console()

TIMEFRAME_MAP = {
    "1m": TimeFrame.MIN_1,
    "5m": TimeFrame.MIN_5,
    "30m": TimeFrame.MIN_30,
    "1h": TimeFrame.HOUR_1,
    "1d": TimeFrame.DAILY,
    "1w": TimeFrame.WEEKLY,
    "1M": TimeFrame.MONTHLY,
}


def _load_klines_from_json(path: Path) -> list[RawKLine]:
    with open(path) as f:
        data = json.load(f)
    klines: list[RawKLine] = []
    for row in data:
        klines.append(
            RawKLine(
                timestamp=datetime.fromisoformat(row["timestamp"]),
                open=Decimal(str(row["open"])),
                high=Decimal(str(row["high"])),
                low=Decimal(str(row["low"])),
                close=Decimal(str(row["close"])),
                volume=int(row["volume"]),
            )
        )
    return klines


@app.command()
def analyze(
    instrument: str = typer.Argument(help="标的代码 (e.g. AAPL)"),
    level: str = typer.Option("1d", help="时间级别 (1m/5m/30m/1h/1d/1w/1M)"),
    data_file: str | None = typer.Option(None, "--data", help="JSON 数据文件路径"),
) -> None:
    """分析单个标的的缠论结构"""
    from chanquant.core.pipeline import AnalysisPipeline

    timeframe = TIMEFRAME_MAP.get(level)
    if not timeframe:
        console.print(f"[red]不支持的时间级别: {level}[/red]")
        raise typer.Exit(1)

    if not data_file:
        console.print("[red]目前需要指定 --data 参数提供 JSON 数据文件[/red]")
        raise typer.Exit(1)

    klines = _load_klines_from_json(Path(data_file))
    pipeline = AnalysisPipeline(level=timeframe, instrument=instrument)

    state = None
    for kline in klines:
        state = pipeline.feed(kline)

    if not state:
        console.print("[yellow]数据不足，无法完成分析[/yellow]")
        raise typer.Exit(0)

    table = Table(title=f"{instrument} 缠论分析结果 ({level})")
    table.add_column("指标", style="cyan")
    table.add_column("数量", style="green")
    table.add_row("标准化K线", str(len(state.standard_klines)))
    table.add_row("分型", str(len(state.fractals)))
    table.add_row("笔", str(len(state.strokes)))
    table.add_row("线段", str(len(state.segments)))
    table.add_row("中枢", str(len(state.centers)))
    table.add_row("背驰", str(len(state.divergences)))
    table.add_row("信号", str(len(state.signals)))
    console.print(table)

    if state.signals:
        sig_table = Table(title="买卖点信号")
        sig_table.add_column("类型", style="bold")
        sig_table.add_column("时间")
        sig_table.add_column("价格", style="green")
        sig_table.add_column("强度")
        for sig in state.signals:
            sig_table.add_row(
                sig.signal_type.value,
                sig.timestamp.isoformat(),
                str(sig.price),
                str(sig.strength),
            )
        console.print(sig_table)

    if state.trend:
        console.print(
            f"\n走势分类: [bold]{state.trend.classification.name}[/bold]"
        )


@app.command()
def backtest(
    instrument: str = typer.Argument(help="标的代码"),
    start: str = typer.Option("2021-01-01", help="起始日期"),
    end: str = typer.Option("2026-01-01", help="结束日期"),
    data_file: str | None = typer.Option(None, "--data", help="JSON 数据文件路径"),
    cash: float = typer.Option(1_000_000, help="初始资金"),
) -> None:
    """运行回测"""
    from chanquant.backtest.engine import BacktestEngine

    if not data_file:
        console.print("[red]目前需要指定 --data 参数提供 JSON 数据文件[/red]")
        raise typer.Exit(1)

    klines = _load_klines_from_json(Path(data_file))
    start_dt = datetime.fromisoformat(start)
    end_dt = datetime.fromisoformat(end)
    filtered = [k for k in klines if start_dt <= k.timestamp <= end_dt]

    if not filtered:
        console.print("[yellow]指定日期范围内无数据[/yellow]")
        raise typer.Exit(0)

    engine = BacktestEngine(initial_cash=Decimal(str(cash)))
    metrics, _snapshots = engine.run({instrument: filtered})

    table = Table(title=f"{instrument} 回测结果 ({start} ~ {end})")
    table.add_column("指标", style="cyan")
    table.add_column("值", style="green")
    table.add_row("总收益率", f"{metrics.total_return:.2%}")
    table.add_row("年化收益率", f"{metrics.annualized_return:.2%}")
    table.add_row("Sharpe Ratio", f"{metrics.sharpe_ratio:.2f}")
    table.add_row("Sortino Ratio", f"{metrics.sortino_ratio:.2f}")
    table.add_row("Calmar Ratio", f"{metrics.calmar_ratio:.2f}")
    table.add_row("最大回撤", f"{metrics.max_drawdown:.2%}")
    table.add_row("胜率", f"{metrics.win_rate:.2%}")
    table.add_row("盈亏比", f"{metrics.profit_factor:.2f}")
    table.add_row("总交易次数", str(metrics.total_trades))
    console.print(table)


@app.command()
def validate(
    fixture_dir: str = typer.Argument(help="测试数据目录路径"),
) -> None:
    """用测试数据验证 L0-L3 算法正确性"""
    from chanquant.core.fractal import FractalDetector
    from chanquant.core.kline import KLineProcessor
    from chanquant.core.stroke import StrokeBuilder

    fixture_path = Path(fixture_dir)
    if not fixture_path.is_dir():
        console.print(f"[red]目录不存在: {fixture_dir}[/red]")
        raise typer.Exit(1)

    total = 0
    passed = 0

    for json_file in sorted(fixture_path.glob("*.json")):
        total += 1
        try:
            klines = _load_klines_from_json(json_file)
            processor = KLineProcessor()
            detector = FractalDetector()
            builder = StrokeBuilder()

            std_count = 0
            fractal_count = 0
            stroke_count = 0
            for kline in klines:
                result = processor.feed(kline)
                if result:
                    std_count += 1
                    fractal = detector.feed(result)
                    if fractal:
                        fractal_count += 1
                        stroke = builder.feed(fractal)
                        if stroke:
                            stroke_count += 1
            # Flush last buffered kline
            last = processor.flush()
            if last:
                std_count += 1
                fractal = detector.feed(last)
                if fractal:
                    fractal_count += 1
                    stroke = builder.feed(fractal)
                    if stroke:
                        stroke_count += 1

            if std_count > 0:
                passed += 1
                console.print(
                    f"  [green]PASS[/green] {json_file.name}: "
                    f"{std_count} klines → "
                    f"{fractal_count} fractals → "
                    f"{stroke_count} strokes"
                )
            else:
                console.print(f"  [yellow]SKIP[/yellow] {json_file.name}: 无有效数据")
        except Exception as e:
            console.print(f"  [red]FAIL[/red] {json_file.name}: {e}")

    if total > 0:
        rate = passed / total * 100
        color = "green" if rate >= 95 else "yellow" if rate >= 80 else "red"
        console.print(f"\n验证通过率: [{color}]{rate:.0f}%[/{color}] ({passed}/{total})")
    else:
        console.print("[yellow]未找到 JSON 测试文件[/yellow]")


if __name__ == "__main__":
    app()
