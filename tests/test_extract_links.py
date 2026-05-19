"""测试_extract_topology_links逻辑"""
import re

def _extract_topology_links(text, local_name):
    """从LLDP/CDP输出提取拓扑链接"""
    links = []
    if not text or not local_name:
        return links

    # H3C/华为 list格式: 表格行
    if re.search(
        r"Local(?:If| Interface)\s+(?:Nbr\s+)?(?:Chassis|chassis)\s+ID",
        text,
        re.IGNORECASE,
    ):
        for line in text.strip().split("\n"):
            # 跳过表头行
            if re.match(r"Local", line.strip(), re.IGNORECASE):
                continue
            # 4列匹配
            m = re.match(
                r"((?:GE|XGE|10GE|40GE|100GE|Eth|Ethernet|GigabitEthernet)\S+)\s+(\S+)\s+(\S+)\s+(\S+)",
                line.strip(),
            )
            if m:
                links.append(
                    {
                        "from_name": local_name,
                        "from_port": m.group(1),
                        "to_name": m.group(4),
                        "to_port": m.group(3),
                        "chassis_id": m.group(2),
                    }
                )
                continue
            # 3列匹配
            m = re.match(
                r"((?:GE|XGE|10GE|40GE|100GE|Eth|Ethernet|GigabitEthernet)\S+)\s+(\S+)\s+(\S+)",
                line.strip(),
            )
            if m:
                links.append(
                    {
                        "from_name": local_name,
                        "from_port": m.group(1),
                        "to_name": "",
                        "to_port": m.group(3),
                        "chassis_id": m.group(2),
                    }
                )
        if links:
            return links
    return links

# 实际LLDP输出
test_data = {
    "接入交换机": """display lldp neighbor-information list
Chassis ID : * -- -- Nearest nontpmr bridge neighbor
             # -- -- Nearest customer bridge neighbor
             Default -- -- Nearest bridge neighbor
Local Interface Chassis ID      Port ID                         System Name     
GE1/0/1         6874-2a6b-0200  GigabitEthernet1/0/1            H3C
GE1/0/2         6874-2a6b-0200  GigabitEthernet1/0/3            H3C
<H3C>""",

    "核心交换机": """display lldp neighbor-information list
Chassis ID : * -- -- Nearest nontpmr bridge neighbor
             # -- -- Nearest customer bridge neighbor
             Default -- -- Nearest bridge neighbor
Local Interface Chassis ID      Port ID                         System Name     
GE1/0/1         6873-af13-0100  GigabitEthernet1/0/1            H3C
GE1/0/2         6874-dafe-0300  GigabitEthernet0/0/0            H3C
GE1/0/3         6873-af13-0100  GigabitEthernet1/0/2            H3C
<H3C>""",

    "出口路": """display lldp neighbor-information list
Chassis ID : * -- -- Nearest nontpmr bridge neighbor
             # -- -- Nearest customer bridge neighbor
             Default -- -- Nearest bridge neighbor
LocalIf         Nbr chassis ID  Nbr port ID                     Nbr system name 
GE0/0/0         6874-2a6b-0200  GigabitEthernet1/0/2            H3C
<H3C>""",
}

for name, output in test_data.items():
    links = _extract_topology_links(output, name)
    print(f"\n{name}: parsed {len(links)} links")
    for l in links:
        print(f"  {l}")
