import xml.etree.ElementTree as ET
import json
from itertools import combinations


def parse_eagle_sch(path: str):
    tree = ET.parse(path)
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
        for net in sheet.findall("./nets/net"):
            net_name = net.attrib.get("name", "")
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


if __name__ == "__main__":
    parsed = parse_eagle_sch("UNO-TH_Rev3e.sch")
    parsed["edges"] = build_pairwise_edges(parsed)

    with open("parsed_netlist.json", "w", encoding="utf-8") as f:
        json.dump(parsed, f, indent=2, ensure_ascii=False)

    print("완료: parsed_netlist.json 생성")