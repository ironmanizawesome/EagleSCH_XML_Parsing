import xml.etree.ElementTree as ET
import json
import re
from itertools import combinations
from pathlib import Path


def load_and_clean_xml(path: str):
    """
    XML 1.0에서 허용되지 않는 제어문자를 제거한 뒤 파싱한다.
    """
    text = Path(path).read_text(encoding="utf-8", errors="replace")

    # XML 1.0에서 허용되지 않는 제어문자 제거
    # 허용 안 되는 범위: 0x00-0x08, 0x0B, 0x0C, 0x0E-0x1F
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', '', text)

    return ET.ElementTree(ET.fromstring(text))


def parse_eagle_sch(path: str):
    tree = load_and_clean_xml(path)
    root = tree.getroot()

    schematic = root.find("./drawing/schematic")
    if schematic is None:
        raise ValueError("schematic 노드를 찾지 못했습니다. EAGLE .sch 파일인지 확인하세요.")

    # 1) parts 추출
    parts = {}
    for part in schematic.findall("./parts/part"):
        name = part.attrib["name"]
        parts[name] = {
            "part": name,
            "library": part.attrib.get("library"),
            "deviceset": part.attrib.get("deviceset"),
            "device": part.attrib.get("device"),
            "technology": part.attrib.get("technology", ""),
            "value": part.attrib.get("value")
        }

    # 2) nets -> members 추출
    nets = []
    for sheet_idx, sheet in enumerate(schematic.findall("./sheets/sheet"), start=1):
        for net_idx, net in enumerate(sheet.findall("./nets/net"), start=1):
            net_name = net.attrib.get("name", f"NET_{sheet_idx}_{net_idx}")
            members = []

            for segment in net.findall("./segment"):
                for pinref in segment.findall("./pinref"):
                    part_name = pinref.attrib["part"]
                    gate_name = pinref.attrib["gate"]
                    pin_name = pinref.attrib["pin"]

                    members.append({
                        "part": part_name,
                        "gate": gate_name,
                        "pin": pin_name,
                        "node_id": f"{part_name}:{gate_name}:{pin_name}"
                    })

            nets.append({
                "sheet": sheet_idx,
                "net": net_name,
                "members": members
            })

    return {
        "source_file": Path(path).name,
        "parts": list(parts.values()),
        "nets": nets
    }


def build_pairwise_edges(parsed):
    edges = []
    for net_obj in parsed["nets"]:
        net_name = net_obj["net"]
        node_ids = [m["node_id"] for m in net_obj["members"]]

        # 같은 net 안의 핀들을 clique 형태로 edge 생성
        for a, b in combinations(sorted(set(node_ids)), 2):
            edges.append({
                "source": a,
                "target": b,
                "net": net_name
            })
    return edges


def parse_all_eagle_sch(input_dir="eagle", output_dir="eagle_parsed"):
    input_path = Path(input_dir)
    output_path = Path(output_dir)

    if not input_path.exists():
        raise FileNotFoundError(f"입력 폴더가 존재하지 않습니다: {input_path}")

    output_path.mkdir(parents=True, exist_ok=True)

    sch_files = sorted(input_path.glob("*.sch"))

    if not sch_files:
        print(f"'{input_path}' 폴더 안에 .sch 파일이 없습니다.")
        return

    success_count = 0
    fail_count = 0

    for sch_file in sch_files:
        try:
            parsed = parse_eagle_sch(str(sch_file))
            parsed["edges"] = build_pairwise_edges(parsed)

            output_file = output_path / f"{sch_file.stem}_parsed.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(parsed, f, indent=2, ensure_ascii=False)

            print(f"[완료] {sch_file.name} -> {output_file.name}")
            success_count += 1

        except Exception as e:
            print(f"[실패] {sch_file.name}: {e}")
            fail_count += 1

    print("\n=== 작업 종료 ===")
    print(f"성공: {success_count}개")
    print(f"실패: {fail_count}개")
    print(f"출력 폴더: {output_path.resolve()}")


if __name__ == "__main__":
    parse_all_eagle_sch("eagle", "eagle_parsed")