"""CLI entry point — `shl` command."""

from __future__ import annotations

import logging
from pathlib import Path

import click
from dotenv import load_dotenv


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="ログレベルをDEBUGに")
def main(verbose: bool) -> None:
    """speech-habit-lens — 1分間スピーチの癖を可視化"""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )


@main.command()
@click.argument("wav_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--out",
    "out_path",
    type=click.Path(path_type=Path),
    default=None,
    help="出力Markdownパス（指定なしならstdout）",
)
@click.option("--model", default="claude-sonnet-4-6", show_default=True, help="Claude model ID")
@click.option("--no-esas", is_flag=True, help="ESAS無効化（音響層がスキップされる）")
def analyze(wav_path: Path, out_path: Path | None, model: str, no_esas: bool) -> None:
    """WAVファイルを解析してMarkdownレポートを出力する"""
    load_dotenv()

    from .analyze import analyze as run_analysis
    from .esas import parse_esas
    from .recognize import recognize
    from .report import to_markdown

    click.echo(f"→ Recognizing {wav_path}...")
    rec = recognize(wav_path, esas=not no_esas)
    click.echo(f"  ✓ {rec.duration_ms / 1000:.1f}s, {len(rec.segments)} segments")

    esas_timeline = parse_esas(rec.raw_response)
    click.echo(f"  ✓ ESAS: {len(esas_timeline.samples)} samples")

    click.echo(f"→ Analyzing with {model}...")
    analysis = run_analysis(rec, esas_timeline, model=model)
    click.echo("  ✓ acoustic / text / cross layers complete")

    click.echo("→ Generating report...")
    report = to_markdown(analysis)

    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
        click.echo(f"  ✓ Wrote {out_path}")
    else:
        click.echo("")
        click.echo(report)


@main.command()
@click.option("--port", default=8501, show_default=True, type=int, help="Streamlit port")
def serve(port: int) -> None:
    """Streamlit UIを起動（v0.2予定）"""
    raise click.UsageError("Streamlit UI is planned for v0.2 — not yet implemented.")


if __name__ == "__main__":
    main()
