#!/usr/bin/env python3
"""
从发票文件中提取文本
支持 PDF（pdfplumber 文本提取 → pdf2image + pytesseract OCR 兜底）和图片（pytesseract OCR）
输出提取的文本到 stdout。

用法:
    python3 extract_text.py <文件路径>

输出:
    提取的文本，输出到 stdout
"""

import sys
import os
import argparse


def extract_from_pdf(pdf_path: str) -> str:
    """从 PDF 提取文本：先尝试 pdfplumber，文本太少则回退到 OCR"""
    # 第一步：pdfplumber 文本提取
    text = ""
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text += page_text + "\n"
    except Exception as e:
        sys.stderr.write(f"pdfplumber 提取失败: {e}\n")

    # 如果提取的文本足够丰富，直接返回
    if len(text.strip()) > 100:
        return text

    # 第二步：pdf2image + pytesseract OCR
    sys.stderr.write("pdfplumber 文本不足，回退到 OCR 方案\n")
    try:
        from pdf2image import convert_from_path
        import pytesseract

        images = convert_from_path(pdf_path, dpi=300)
        for img in images:
            page_text = pytesseract.image_to_string(img, lang="chi_sim+eng")
            text += page_text + "\n"
    except Exception as e:
        sys.stderr.write(f"OCR 提取失败: {e}\n")

    return text


def extract_from_image(img_path: str) -> str:
    """从图片提取文本：pytesseract OCR"""
    try:
        from PIL import Image
        import pytesseract

        img = Image.open(img_path)
        text = pytesseract.image_to_string(img, lang="chi_sim+eng")
        return text
    except Exception as e:
        sys.stderr.write(f"图片 OCR 失败: {e}\n")
        return ""


def main():
    parser = argparse.ArgumentParser(description="从发票文件提取文本")
    parser.add_argument("file_path", help="发票文件路径（PDF 或图片）")
    args = parser.parse_args()

    if not os.path.exists(args.file_path):
        sys.stderr.write(f"文件不存在: {args.file_path}\n")
        sys.exit(1)

    ext = os.path.splitext(args.file_path)[1].lower()

    if ext == ".pdf":
        text = extract_from_pdf(args.file_path)
    elif ext in (".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"):
        text = extract_from_image(args.file_path)
    else:
        sys.stderr.write(f"不支持的文件格式: {ext}\n")
        sys.exit(1)

    print(text)


if __name__ == "__main__":
    main()