"""
厂商识别模块
根据设备SNMP信息和命令输出自动识别厂商、型号、设备类型
"""
import re
from typing import Optional, Dict, Any, List, Tuple
from app.core.device import Vendor, DeviceType


class VendorIdentifier:
    """厂商识别器"""
    
    # 厂商SNMP OID前缀映射
    VENDOR_OID_MAP = {
        "1.3.6.1.4.1.2011": Vendor.HUAWEI,
        "1.3.6.1.4.1.25506": Vendor.H3C,
        "1.3.6.1.4.1.9": Vendor.CISCO,
        "1.3.6.1.4.1.2636": Vendor.JUNIPER,
        "1.3.6.1.4.1.4881": Vendor.RUIJIE,
    }
    
    # 厂商特征字符串
    VENDOR_KEYWORDS = {
        Vendor.HUAWEI: ["huawei", "huawei technologies", "huawei tech"],
        Vendor.H3C: ["h3c", "hp networking", "3com"],
        Vendor.CISCO: ["cisco", "cisco systems"],
        Vendor.JUNIPER: ["juniper", "juniper networks"],
        Vendor.RUIJIE: ["ruijie", "ruijie networks"],
    }
    
    # 设备类型关键词映射
    DEVICE_TYPE_KEYWORDS = {
        DeviceType.ROUTER: ["router", "msr", "ar", "ne", "asr", "7600", "7200"],
        DeviceType.SWITCH_L3: ["l3", "三层", "layer 3", "s57", "s67", "9300", "9500", "l3 switch"],
        DeviceType.SWITCH_L2: ["switch", "s17", "s27", "s37", "s57", "2960", "3750", "2950"],
        DeviceType.FIREWALL: ["firewall", "usg", "nip", "asa", "fortigate", "fw"],
        DeviceType.LOAD_BALANCER: ["load balancer", "lb", "adc", "f5", "a10"],
    }
    
    # 华为型号系列
    HUAWEI_MODEL_SERIES = {
        "s1700": DeviceType.SWITCH_L2,
        "s2700": DeviceType.SWITCH_L2,
        "s3700": DeviceType.SWITCH_L2,
        "s5700": DeviceType.SWITCH_L2,
        "s5700s": DeviceType.SWITCH_L2,
        "s5720": DeviceType.SWITCH_L2,
        "s5735": DeviceType.SWITCH_L2,
        "s6700": DeviceType.SWITCH_L3,
        "s6720": DeviceType.SWITCH_L3,
        "s6730": DeviceType.SWITCH_L3,
        "s6735": DeviceType.SWITCH_L3,
        "s9300": DeviceType.SWITCH_L3,
        "s9300x": DeviceType.SWITCH_L3,
        "s9700": DeviceType.SWITCH_L3,
        "s12700": DeviceType.SWITCH_L3,
        "s12700x": DeviceType.SWITCH_L3,
        "ar1220": DeviceType.ROUTER,
        "ar2220": DeviceType.ROUTER,
        "ar2240": DeviceType.ROUTER,
        "ar3260": DeviceType.ROUTER,
        "ar5220": DeviceType.ROUTER,
        "ne": DeviceType.ROUTER,
        "me60": DeviceType.ROUTER,
        "usg": DeviceType.FIREWALL,
        "nip": DeviceType.FIREWALL,
        "secospace": DeviceType.FIREWALL,
    }
    
    # 思科型号系列
    CISCO_MODEL_SERIES = {
        "2960": DeviceType.SWITCH_L2,
        "2965": DeviceType.SWITCH_L2,
        "2970": DeviceType.SWITCH_L2,
        "3550": DeviceType.SWITCH_L3,
        "3560": DeviceType.SWITCH_L2,
        "3650": DeviceType.SWITCH_L3,
        "3750": DeviceType.SWITCH_L2,
        "3850": DeviceType.SWITCH_L3,
        "4500": DeviceType.SWITCH_L3,
        "6500": DeviceType.SWITCH_L3,
        "6800": DeviceType.SWITCH_L3,
        "6900": DeviceType.SWITCH_L3,
        "9000": DeviceType.SWITCH_L3,
        "9200": DeviceType.SWITCH_L3,
        "9300": DeviceType.SWITCH_L3,
        "9500": DeviceType.SWITCH_L3,
        "9600": DeviceType.SWITCH_L3,
        "1700": DeviceType.ROUTER,
        "1800": DeviceType.ROUTER,
        "1900": DeviceType.ROUTER,
        "2800": DeviceType.ROUTER,
        "2900": DeviceType.ROUTER,
        "3800": DeviceType.ROUTER,
        "3900": DeviceType.ROUTER,
        "4000": DeviceType.ROUTER,
        "4300": DeviceType.ROUTER,
        "4400": DeviceType.ROUTER,
        "7200": DeviceType.ROUTER,
        "7300": DeviceType.ROUTER,
        "7600": DeviceType.ROUTER,
        "asr": DeviceType.ROUTER,
        "asa": DeviceType.FIREWALL,
        "firepower": DeviceType.FIREWALL,
        "meraki": DeviceType.SWITCH_L2,
    }
    
    # 华三型号系列
    H3C_MODEL_SERIES = {
        "s3100": DeviceType.SWITCH_L2,
        "s3600": DeviceType.SWITCH_L2,
        "s5130": DeviceType.SWITCH_L2,
        "s5150": DeviceType.SWITCH_L2,
        "s5500": DeviceType.SWITCH_L3,
        "s5560": DeviceType.SWITCH_L3,
        "s5600": DeviceType.SWITCH_L3,
        "s5800": DeviceType.SWITCH_L3,
        "s5900": DeviceType.SWITCH_L3,
        "s6300": DeviceType.SWITCH_L3,
        "s6520": DeviceType.SWITCH_L3,
        "s6550": DeviceType.SWITCH_L3,
        "s7500": DeviceType.SWITCH_L3,
        "s8500": DeviceType.SWITCH_L3,
        "s10500": DeviceType.SWITCH_L3,
        "msr": DeviceType.ROUTER,
        "msr20": DeviceType.ROUTER,
        "msr30": DeviceType.ROUTER,
        "msr3600": DeviceType.ROUTER,
        "secpath": DeviceType.FIREWALL,
        "fw": DeviceType.FIREWALL,
    }
    
    @classmethod
    def identify_from_snmp(cls, sys_descr: str = "", sys_object_id: str = "") -> Tuple[Vendor, str, DeviceType]:
        """
        根据SNMP信息识别厂商
        
        Args:
            sys_descr: sysDescr (如: "Huawei S5720S-28P-SI Ver V200R019C10...")
            sys_object_id: sysObjectID (如: .1.3.6.1.4.1.2011.2.279.5)
        
        Returns:
            (厂商, 型号, 设备类型)
        """
        vendor = Vendor.UNKNOWN
        model = ""
        device_type = DeviceType.UNKNOWN
        
        # 1. 根据sysObjectID识别
        if sys_object_id:
            for oid_prefix, vend in cls.VENDOR_OID_MAP.items():
                if sys_object_id.startswith(oid_prefix):
                    vendor = vend
                    break
        
        # 2. 根据sysDescr识别厂商
        if sys_descr:
            sys_descr_lower = sys_descr.lower()
            
            # 识别厂商
            if vendor == Vendor.UNKNOWN:
                for vend, keywords in cls.VENDOR_KEYWORDS.items():
                    for keyword in keywords:
                        if keyword in sys_descr_lower:
                            vendor = vend
                            break
                    if vendor != Vendor.UNKNOWN:
                        break
            
            # 提取型号
            model = cls._extract_model(sys_descr)
            
            # 识别设备类型
            device_type = cls._identify_device_type(model, sys_descr)
        
        return vendor, model, device_type
    
    @classmethod
    def _extract_model(cls, sys_descr: str) -> str:
        """从sysDescr提取型号"""
        # 常见模式: "Huawei S5720S-28P-SI Ver V200R019C10"
        #           "Cisco IOS Software, C2960"
        
        # 匹配华为型号
        huawei_patterns = [
            r'(S\d{4}[A-Z]?-\d+[A-Z]?)',  # S5720S-28P
            r'(S\d{5}[A-Z]?)',              # S5735S
            r'(AR\d{4})',                   # AR1220
            r'(NE\d+)',                     # NE40E
            r'(USG\d+)',                    # USG6000
        ]
        
        # 思科型号
        cisco_patterns = [
            r'(C\d{4})',                    # C2960
            r'([A-Z]\d{3})',               # 2960
            r'(ASR\s*\d+)',                # ASR 1000
            r'(ISR\s*\d+)',                # ISR 4000
        ]
        
        for pattern in huawei_patterns:
            match = re.search(pattern, sys_descr, re.IGNORECASE)
            if match:
                return match.group(1).upper()
        
        for pattern in cisco_patterns:
            match = re.search(pattern, sys_descr, re.IGNORECASE)
            if match:
                return match.group(1)
        
        # 尝试提取第一个连续字母数字组合作为型号
        match = re.search(r'([A-Za-z0-9]+(?:[A-Za-z0-9-]+)?)', sys_descr)
        if match:
            return match.group(1)
        
        return ""
    
    @classmethod
    def _identify_device_type(cls, model: str, sys_descr: str) -> DeviceType:
        """识别设备类型"""
        text = f"{model} {sys_descr}".lower()
        
        # 先匹配型号
        if model:
            # 华为
            for series, dtype in cls.HUAWEI_MODEL_SERIES.items():
                if series in text:
                    return dtype
            
            # 思科
            for series, dtype in cls.CISCO_MODEL_SERIES.items():
                if series in text.lower():
                    return dtype
            
            # 华三
            for series, dtype in cls.H3C_MODEL_SERIES.items():
                if series in text.lower():
                    return dtype
        
        # 再匹配关键词
        for dtype, keywords in cls.DEVICE_TYPE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text:
                    return dtype
        
        return DeviceType.UNKNOWN
    
    @classmethod
    def identify_from_command_output(cls, version_output: str) -> Tuple[Vendor, str, DeviceType]:
        """
        根据命令输出识别厂商和型号
        
        Args:
            version_output: 设备版本信息输出
        
        Returns:
            (厂商, 型号, 设备类型)
        """
        return cls.identify_from_snmp(sys_descr=version_output)
    
    @classmethod
    def get_vendor_display_name(cls, vendor: Vendor) -> str:
        """获取厂商显示名称"""
        names = {
            Vendor.HUAWEI: "华为",
            Vendor.H3C: "华三",
            Vendor.CISCO: "思科",
            Vendor.JUNIPER: "Juniper",
            Vendor.RUIJIE: "锐捷",
            Vendor.UNKNOWN: "未知",
        }
        return names.get(vendor, "未知")
    
    @classmethod
    def get_device_type_display_name(cls, device_type: DeviceType) -> str:
        """获取设备类型显示名称"""
        names = {
            DeviceType.ROUTER: "路由器",
            DeviceType.SWITCH_L3: "三层交换机",
            DeviceType.SWITCH_L2: "二层交换机",
            DeviceType.FIREWALL: "防火墙",
            DeviceType.SERVER: "服务器",
            DeviceType.LOAD_BALANCER: "负载均衡器",
            DeviceType.WIRELESS_AP: "无线AP",
            DeviceType.ENDPOINT: "终端设备",
            DeviceType.UNKNOWN: "未知设备",
        }
        return names.get(device_type, "未知设备")