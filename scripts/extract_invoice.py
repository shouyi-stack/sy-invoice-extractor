#!/usr/bin/env python3
"""
发票信息提取脚本
从文本文件中读取发票文本（由 pdfplumber 或 pytesseract 提取），用正则表达式解析结构化字段。
输出 JSON 到 stdout。

用法:
    python3 extract_invoice.py <text-file-path> [--file-name <原始文件名>]

输出:
    JSON 格式的发票信息，输出到 stdout
"""

import json
import re
import sys
import argparse


def normalize_text(text: str) -> str:
    """清理文本：统一空白、全角转半角，但保留换行结构"""
    # 全角空格转半角
    text = text.replace("\u3000", " ")
    # 全角数字字母转半角
    fullwidth = "０１２３４５６７８９ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ"
    halfwidth = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    trans = str.maketrans(fullwidth, halfwidth)
    text = text.translate(trans)
    # 合并连续空格（但保留换行）
    text = re.sub(r"[ \t]+", " ", text)
    # 去除每行首尾空格
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(lines)
    return text


def extract_invoice_type(text: str) -> str | None:
    """提取发票类型"""
    # 优先匹配更具体的类型
    if "增值税电子专用发票" in text:
        return "增值税电子专用发票"
    if "增值税电子普通发票" in text:
        return "增值税电子普通发票"
    if "增值税专用发票" in text:
        return "增值税专用发票"
    if "增值税普通发票" in text:
        return "增值税普通发票"
    return None


def extract_invoice_code(text: str) -> str | None:
    """提取发票代码：10位或12位数字"""
    # 方式1："发票代码" 标签后紧跟的数字
    patterns = [
        r"发票代码[:：\s]*(\d{10,12})",
        r"发票代码\s*(\d{10,12})",
        r"代\s*码[:：\s]*(\d{10,12})",
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(1)
    # 方式2：在文本前部区域单独出现的10位或12位数字行
    # 取前 20 行查找
    head = "\n".join(text.split("\n")[:20])
    for line in head.split("\n"):
        line = line.strip()
        if re.fullmatch(r"\d{10,12}", line):
            return line
    return None


def extract_invoice_number(text: str) -> str | None:
    """提取发票号码：8位数字"""
    patterns = [
        r"发票号码[:：\s]*(\d{8})",
        r"发票号码\s*(\d{8})",
        r"号\s*码[:：\s]*(\d{8})",
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(1)
    # 兜底：前20行中单独出现的8位数字
    head = "\n".join(text.split("\n")[:20])
    for line in head.split("\n"):
        line = line.strip()
        if re.fullmatch(r"\d{8}", line):
            return line
    return None


def extract_invoice_date(text: str) -> str | None:
    """提取开票日期，统一输出 YYYY-MM-DD"""
    patterns = [
        r"开票日期[:：\s]*(\d{4})年(\d{1,2})月(\d{1,2})日",
        r"开票日期[:：\s]*(\d{4})-(\d{1,2})-(\d{1,2})",
        r"开票日期[:：\s]*(\d{4})/(\d{1,2})/(\d{1,2})",
        r"开票日期\s*(\d{4})年(\d{1,2})月(\d{1,2})日",
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            y, mo, d = m.group(1), int(m.group(2)), int(m.group(3))
            return f"{y}-{mo:02d}-{d:02d}"
    # 兜底：任何 YYYY年MM月DD日
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", text)
    if m:
        y, mo, d = m.group(1), int(m.group(2)), int(m.group(3))
        return f"{y}-{mo:02d}-{d:02d}"
    return None


def extract_buyer_name(text: str) -> str | None:
    """提取购买方名称"""
    patterns = [
        r"购\s*买\s*方.*?名\s*称[:：\s]*(.+?)(?:\s|$|\n)",
        r"名称[:：\s]*(.+?)(?:\s|$|\n)",
    ]
    # 先尝试在"购买方"上下文中匹配
    buyer_section = ""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if "购买方" in line or "购买方" in "".join(lines[max(0, i - 1):i + 3]):
            buyer_section = "\n".join(lines[i:i + 5])
            break
    if buyer_section:
        for p in patterns:
            m = re.search(p, buyer_section)
            if m:
                name = m.group(1).strip()
                # 清理掉后续标签文字
                name = re.split(r"纳税人识别号|税号|地址|电话|开户行", name)[0].strip()
                if name and len(name) >= 2:
                    return name
    # 全文兜底
    for p in patterns:
        m = re.search(p, text)
        if m:
            name = m.group(1).strip()
            name = re.split(r"纳税人识别号|税号|地址|电话|开户行", name)[0].strip()
            if name and len(name) >= 2:
                return name
    return None


def extract_seller_name(text: str) -> str | None:
    """提取销售方名称"""
    patterns = [
        r"销\s*售\s*方.*?名\s*称[:：\s]*(.+?)(?:\s|$|\n)",
        r"名称[:：\s]*(.+?)(?:\s|$|\n)",
    ]
    # 在"销售方"上下文中匹配
    seller_section = ""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if "销售方" in line or "销售方" in "".join(lines[max(0, i - 1):i + 3]):
            seller_section = "\n".join(lines[i:i + 5])
            break
    if seller_section:
        for p in patterns:
            m = re.search(p, seller_section)
            if m:
                name = m.group(1).strip()
                name = re.split(r"纳税人识别号|税号|地址|电话|开户行", name)[0].strip()
                if name and len(name) >= 2:
                    return name
    return None


def extract_tax_id(text: str, party: str) -> str | None:
    """提取纳税人识别号。party: 'buyer' 或 'seller'"""
    party_label = "购买方" if party == "buyer" else "销售方"
    patterns = [
        rf"{party_label}.*?纳税人识别号[:：\s]*([A-Za-z0-9]{{6,20}})",
        rf"纳税人识别号[:：\s]*([A-Za-z0-9]{{6,20}})",
        rf"统一社会信用代码[:：\s]*([A-Za-z0-9]{{6,20}})",
        rf"税\s*号[:：\s]*([A-Za-z0-9]{{6,20}})",
    ]
    # 先在对应方的上下文中匹配
    section = ""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if party_label in line:
            section = "\n".join(lines[i:i + 6])
            break
    if section:
        for p in patterns:
            m = re.search(p, section, re.DOTALL)
            if m:
                return m.group(1).strip()
    # 全文兜底
    for p in patterns:
        m = re.search(p, text, re.DOTALL)
        if m:
            return m.group(1).strip()
    return None


def extract_amount(text: str) -> float | None:
    """提取金额（不含税）"""
    patterns = [
        r"金额[:：\s]*¥?([\d,]+\.?\d*)",
        r"合计[:：\s]*¥?([\d,]+\.?\d*)\s+¥?([\d,]+\.?\d*)",  # 合计行：金额 税额
        r"合\s*计\s*¥?([\d,]+\.?\d*)",
    ]
    # 匹配 "金额" 标签后第一个数字（排除"价税合计"）
    # 先找 "金额" 行
    m = re.search(r"(?<!价税)金额[:：\s]*¥?([\d,]+\.?\d*)", text)
    if m:
        return parse_amount(m.group(1))
    # 合计行
    m = re.search(r"合\s*计\s*¥?([\d,]+\.?\d*)\s+¥?([\d,]+\.?\d*)", text)
    if m:
        return parse_amount(m.group(1))
    return None


def extract_tax_amount(text: str) -> float | None:
    """提取税额"""
    m = re.search(r"税\s*额[:：\s]*¥?([\d,]+\.?\d*)", text)
    if m:
        return parse_amount(m.group(1))
    # 合计行：第二个数字
    m = re.search(r"合\s*计\s*¥?([\d,]+\.?\d*)\s+¥?([\d,]+\.?\d*)", text)
    if m:
        return parse_amount(m.group(2))
    return None


def extract_tax_rate(text: str) -> float | None:
    """提取税率"""
    # 匹配 13% 9% 6% 3% 1% 0% 等
    m = re.search(r"(\d{1,2})%\s*[\d,]+\.?\d*", text)
    if m:
        return int(m.group(1)) / 100
    # 匹配 0.13 0.09 等小数形式
    m = re.search(r"(0\.\d{2})\s*[\d,]+\.?\d*", text)
    if m:
        return float(m.group(1))
    return None


def extract_total_amount(text: str) -> float | None:
    """提取价税合计"""
    patterns = [
        r"价税合计[（(]大写[)）].*?[（(]小写[)）][:：\s]*¥?([\d,]+\.?\d*)",
        r"价税合计.*?¥?([\d,]+\.?\d*)",
        r"\（小写）\s*¥?([\d,]+\.?\d*)",
        r"\(小写\)\s*¥?([\d,]+\.?\d*)",
    ]
    for p in patterns:
        m = re.search(p, text, re.DOTALL)
        if m:
            return parse_amount(m.group(1))
    return None


def extract_check_code(text: str) -> str | None:
    """提取校验码"""
    patterns = [
        r"校验码[:：\s]*(\d{6,20})",
        r"校验码\s*[:：]?\s*(\d{6,20})",
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(1).strip()
    return None


def parse_amount(s: str) -> float:
    """将金额字符串转为浮点数"""
    s = s.replace(",", "").replace("¥", "").replace("￥", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def validate_fields(data: dict) -> list[str]:
    """校验提取结果，返回错误信息列表"""
    errors = []

    if data.get("invoice_code"):
        if not re.fullmatch(r"\d{10,12}", data["invoice_code"]):
            errors.append(f"invoice_code: 格式异常（{data['invoice_code']}），应为10位或12位数字")

    if data.get("invoice_number"):
        if not re.fullmatch(r"\d{8}", data["invoice_number"]):
            errors.append(f"invoice_number: 格式异常（{data['invoice_number']}），应为8位数字")

    # 金额校验：金额 + 税额 ≈ 价税合计
    amount = data.get("amount")
    tax = data.get("tax_amount")
    total = data.get("total_amount")
    if amount is not None and tax is not None and total is not None:
        if abs(amount + tax - total) > 0.02:
            errors.append(
                f"金额校验不一致: 金额({amount}) + 税额({tax}) = {amount + tax}, "
                f"与价税合计({total}) 不符"
            )

    return errors


def extract_all(text: str) -> dict:
    """从文本中提取所有发票字段"""
    text = normalize_text(text)

    data = {
        "invoice_type": extract_invoice_type(text),
        "invoice_code": extract_invoice_code(text),
        "invoice_number": extract_invoice_number(text),
        "invoice_date": extract_invoice_date(text),
        "buyer_name": extract_buyer_name(text),
        "buyer_tax_id": extract_tax_id(text, "buyer"),
        "seller_name": extract_seller_name(text),
        "seller_tax_id": extract_tax_id(text, "seller"),
        "amount": extract_amount(text),
        "tax_rate": extract_tax_rate(text),
        "tax_amount": extract_tax_amount(text),
        "total_amount": extract_total_amount(text),
        "check_code": extract_check_code(text),
    }

    # 记录未识别的字段
    errors = []
    field_labels = {
        "invoice_type": "发票类型",
        "invoice_code": "发票代码",
        "invoice_number": "发票号码",
        "invoice_date": "开票日期",
        "buyer_name": "购买方名称",
        "buyer_tax_id": "购买方税号",
        "seller_name": "销售方名称",
        "seller_tax_id": "销售方税号",
        "amount": "金额",
        "tax_rate": "税率",
        "tax_amount": "税额",
        "total_amount": "价税合计",
        "check_code": "校验码",
    }
    for key, label in field_labels.items():
        if data[key] is None:
            # 校验码是可选字段，不报错
            if key == "check_code":
                continue
            errors.append(f"{key}: 未识别到{label}")

    # 字段格式校验
    errors.extend(validate_fields(data))

    data["extraction_errors"] = errors
    return data


def main():
    parser = argparse.ArgumentParser(description="从文本文件提取发票信息")
    parser.add_argument("text_file", help="包含发票文本的文件路径")
    parser.add_argument("--file-name", default=None, help="原始文件名（用于批量处理标识）")
    args = parser.parse_args()

    try:
        with open(args.text_file, "r", encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        print(json.dumps({
            "file": args.file_name or args.text_file,
            "data": None,
            "error": f"文件不存在: {args.text_file}"
        }, ensure_ascii=False, indent=2))
        sys.exit(1)

    if not text.strip():
        print(json.dumps({
            "file": args.file_name or args.text_file,
            "data": None,
            "error": "提取的文本为空，可能需要使用 OCR 或图片理解工具"
        }, ensure_ascii=False, indent=2))
        sys.exit(1)

    data = extract_all(text)

    if args.file_name:
        result = {
            "file": args.file_name,
            "data": data,
        }
    else:
        result = data

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()