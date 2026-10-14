---
name: invoice-extractor
description: >-
  发票信息提取技能：上传发票图片或 PDF，自动识别发票代码、发票号码、开票日期、购买方、销售方、金额、税额等字段，
  支持增值税普通发票和专用发票，输出结构化 JSON。当用户上传发票文件（图片或PDF）并希望提取其中的关键信息，
  或者用户提到"提取发票""识别发票""发票信息""发票字段""解析发票""发票OCR""发票结构化"等场景时，务必使用本技能。
  即使用户没有明确说"发票信息提取"，只要意图是从发票文件中读取关键字段，也应优先触发本技能。
---

# 发票信息提取技能

## 概述

本技能从用户上传的发票文件（PDF 或图片）中提取结构化信息，输出为标准 JSON 格式。支持增值税普通发票和增值税专用发票，支持批量上传。

## 提取字段

| 字段名 | JSON Key | 说明 |
|--------|----------|------|
| 发票类型 | `invoice_type` | "增值税普通发票" 或 "增值税专用发票" |
| 发票代码 | `invoice_code` | 10位或12位数字 |
| 发票号码 | `invoice_number` | 8位数字 |
| 开票日期 | `invoice_date` | 格式 YYYY-MM-DD |
| 购买方名称 | `buyer_name` | 购买方企业名称 |
| 购买方税号 | `buyer_tax_id` | 购买方纳税人识别号 |
| 销售方名称 | `seller_name` | 销售方企业名称 |
| 销售方税号 | `seller_tax_id` | 销售方纳税人识别号 |
| 金额 | `amount` | 不含税金额，浮点数 |
| 税率 | `tax_rate` | 如 0.13、0.09、0.03 |
| 税额 | `tax_amount` | 税额，浮点数 |
| 价税合计 | `total_amount` | 含税总金额，浮点数 |
| 校验码 | `check_code` | 普通发票后6位或20位校验码（如有） |

## 工作流程

### 第一步：确定文件类型并提取文本

根据用户上传的文件类型选择提取方式：

**电子发票 PDF（首选方案）**：使用 `pdfplumber` 提取文本。电子发票 PDF 通常包含可选中文本层，提取效果最好。
- 如果 pdfplumber 提取出的文本足够丰富（>100字符），直接进入正则解析阶段。
- 如果 pdfplumber 提取文本极少或为空（说明是扫描件 PDF），回退到 OCR 方案。

**图片文件（jpg/png 等）**：使用 `pytesseract` 进行 OCR 文本提取。支持中文：`pytesseract.image_to_string(img, lang='chi_sim+eng')`。

**扫描件 PDF**：先用 `pdf2image` 将 PDF 转为图片，再用 `pytesseract` 进行 OCR。

### 第二步：正则解析提取字段

从提取的文本中，用以下正则模式匹配字段。发票排版有国标格式，这些模式覆盖了大多数情况：

运行技能目录下 `scripts/extract_invoice.py` 脚本，传入提取到的文本文件路径，脚本会输出结构化 JSON。使用方式：

```bash
python3 <skill-dir>/scripts/extract_invoice.py <text-file-path>
```

脚本内部的正则匹配逻辑说明（便于理解和扩展）：

- **发票类型**：匹配 "增值税普通发票" 或 "增值税专用发票"，也兼容 "增值税电子普通发票" 等变体
- **发票代码**：10位或12位纯数字，通常出现在 "发票代码" 标签后
- **发票号码**：8位纯数字，出现在 "发票号码" 标签后
- **开票日期**：匹配 `YYYY年MM月DD日` 或 `YYYY-MM-DD` 格式
- **购买方/销售方名称**：匹配 "名称：" 后的文字
- **购买方/销售方税号**：匹配 "纳税人识别号：" 后的字母数字串
- **金额**：匹配 "金额" 或 "合计" 标签后的数字（非"价税合计"行）
- **税额**：匹配 "税额" 标签后的数字
- **价税合计**：匹配 "价税合计" 后的小写金额
- **校验码**：匹配 "校验码" 后的数字串

### 第三步：后处理与校验

对提取结果进行基本校验：
- 发票代码应为10位或12位纯数字
- 发票号码应为8位纯数字
- 金额 + 税额 应约等于价税合计（允许0.01元误差，浮点精度问题）
- 日期格式统一为 YYYY-MM-DD

如果校验不一致，在 `extraction_errors` 中添加警告信息，但仍然输出提取到的值。

### 第四步：输出 JSON

**单张发票输出格式**：

```json
{
  "invoice_type": "增值税普通发票",
  "invoice_code": "011001700111",
  "invoice_number": "12345678",
  "invoice_date": "2024-03-15",
  "buyer_name": "某某科技有限公司",
  "buyer_tax_id": "91110108MA01ABC23X",
  "seller_name": "某某商贸有限公司",
  "seller_tax_id": "91110105MA02DEF45Y",
  "amount": 1000.00,
  "tax_rate": 0.13,
  "tax_amount": 130.00,
  "total_amount": 1130.00,
  "check_code": "12345678901234567890",
  "extraction_errors": []
}
```

**批量上传输出格式**（多个文件时返回数组）：

```json
[
  { "file": "invoice1.pdf", "data": { ... }, "extraction_errors": [] },
  { "file": "invoice2.jpg", "data": { ... }, "extraction_errors": ["buyer_tax_id: 未识别到纳税人识别号"] }
]
```

**错误处理规则**：
- 无法识别的字段值设为 `null`
- 在 `extraction_errors` 数组中记录每个失败字段的说明，格式为 `"字段名: 失败原因"`
- 如果整个文件无法解析（非发票文件或文件损坏），返回 `{"file": "xxx", "data": null, "error": "无法解析：文件不是有效的发票"}`

## 实现注意事项

- 发票文本提取后可能包含大量空白和换行，正则匹配前需要适当清理文本（去除多余空白、统一全角半角字符），但不要破坏字段间的结构关系。
- 增值税专用发票有"购买方地址、电话"和"购买方开户行及账号"字段，普通发票可能没有。提取时只关注目标字段，忽略其他信息。
- 部分电子发票 PDF 的文本层顺序可能与视觉顺序不一致，导致正则匹配困难。遇到这种情况，可以先用 `mcp__tupianlijie__ImageQuiz` 工具作为兜底方案，将发票图片传给视觉理解模型提取信息。
- 用户上传的文件可能格式不一，始终先尝试 pdfplumber 文本提取，成功则用正则；失败再走 OCR；OCR 仍不行则用图片理解工具兜底。

## 依赖

以下 Python 包需要预先安装（环境可能已预装部分）：

```bash
pip3 install --user --break-system-packages pdfplumber pytesseract pdf2image Pillow
```

系统还需要安装 tesseract-ocr 及中文语言包：

```bash
apt-get install -y tesseract-ocr tesseract-ocr-chi-sim
```

安装前先检查是否已安装：`python3 -c "import pdfplumber; import pytesseract; import pdf2image"`，如果全部成功则无需安装。

## 交互指引

- 用户上传单个文件时，直接提取并以 JSON 格式在对话中返回结果。
- 用户上传多个文件时，逐个提取，汇总为 JSON 数组返回。
- 如果提取结果中有 `extraction_errors`，在 JSON 之后简要提示用户哪些字段可能需要人工核对。
- 用户要求保存结果时，将 JSON 写入文件（如 `invoice_result.json`）保存到工作目录。