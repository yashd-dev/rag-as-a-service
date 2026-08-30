import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).parent
DATASET_DIR = ROOT / "qna" / "dataset"
DEFAULT_OUTPUT = ROOT / "qna" / "dataset.json"


def parse_message_lines(lines: list[str]) -> list[dict]:
    messages = []
    current = None

    for line_number, raw_line in enumerate(lines, start=2):
        line = raw_line.rstrip("\n")
        speaker, separator, content = line.partition(": ")
        if separator and speaker:
            if current:
                current["text"] = "\n".join(current["parts"]).strip()
                current.pop("parts")
                messages.append(current)
            current = {
                "speaker": speaker,
                "line_start": line_number,
                "parts": [content],
            }
            continue

        if current:
            current["parts"].append(line)

    if current:
        current["text"] = "\n".join(current["parts"]).strip()
        current.pop("parts")
        messages.append(current)

    return messages


def parse_txt_file(path: Path) -> dict:
    raw_text = path.read_text(encoding="utf-8")
    lines = raw_text.splitlines()
    if not lines:
        raise ValueError(f"empty file: {path}")

    time_prefix = "Time: "
    raw_timestamp = lines[0][len(time_prefix) :].strip() if lines[0].startswith(time_prefix) else ""
    parsed_at = datetime.strptime(raw_timestamp, "%Y%m%d_%H:%M") if raw_timestamp else None
    messages = parse_message_lines(lines[1:])
    relative_path = path.relative_to(DATASET_DIR)
    section_id = relative_path.parent.as_posix() if relative_path.parent != Path(".") else "root"
    segment_id = path.stem
    participants = sorted({message["speaker"] for message in messages})

    fragments = []
    for index, message in enumerate(messages, start=1):
        fragments.append(
            {
                "fragment_id": f"{section_id}/{segment_id}#{index}",
                "fragment_index": index,
                "speaker": message["speaker"],
                "line_start": message["line_start"],
                "text": message["text"],
            }
        )

    return {
        "file_id": f"{section_id}/{segment_id}",
        "section_id": section_id,
        "segment_id": segment_id,
        "source_path": relative_path.as_posix(),
        "file_name": path.name,
        "raw_timestamp": raw_timestamp,
        "date": parsed_at.strftime("%Y-%m-%d") if parsed_at else None,
        "time": parsed_at.strftime("%H:%M") if parsed_at else None,
        "participants": participants,
        "message_count": len(messages),
        "fragment_count": len(fragments),
        "fragments": fragments,
    }


def build_dataset(dataset_dir: Path) -> dict:
    items = [parse_txt_file(path) for path in sorted(dataset_dir.rglob("*.txt"))]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_dir": dataset_dir.relative_to(ROOT).as_posix(),
        "file_count": len(items),
        "items": items,
    }


def run_self_check() -> None:
    messages = parse_message_lines(
        [
            "Alice: first line",
            "",
            "still Alice",
            "Bob: reply",
        ]
    )
    assert messages == [
        {"speaker": "Alice", "line_start": 2, "text": "first line\n\nstill Alice"},
        {"speaker": "Bob", "line_start": 5, "text": "reply"},
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-dir", type=Path, default=DATASET_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    run_self_check()
    dataset = build_dataset(args.dataset_dir.resolve())
    args.output.write_text(json.dumps(dataset, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {args.output} ({dataset['file_count']} files)", flush=True)


if __name__ == "__main__":
    main()
