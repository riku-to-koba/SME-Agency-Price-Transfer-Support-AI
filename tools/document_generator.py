"""汎用PDF生成ツール（generate_document）

任意の文書内容をPDF形式で出力する汎用ツール。
LLMが作成した長文ドキュメントをそのままPDF化します。
"""
import os
import uuid
from datetime import datetime
from typing import Optional, List
from strands import tool

# 最後に生成されたPDFファイルのパスを保存（バックエンドから参照）
LAST_GENERATED_PDFS: List[str] = []

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.enums import TA_LEFT, TA_CENTER
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    print("⚠️ Warning: reportlab not installed. PDF generation will be disabled.")


def _save_as_pdf(content: str, title: str, document_type: str) -> str:
    """文書内容をPDFとして保存"""
    if not REPORTLAB_AVAILABLE:
        raise ImportError("reportlab is not installed. Please install it with: pip install reportlab")

    # 保存ディレクトリ
    docs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "documents")
    os.makedirs(docs_dir, exist_ok=True)

    # ファイル名をサニタイズ
    safe_title = "".join(c for c in title if c.isalnum() or c in " -_").strip()[:30]
    if not safe_title:
        safe_title = document_type

    # PDFファイル名
    filename = f"{document_type}_{safe_title}_{uuid.uuid4().hex[:8]}.pdf"
    filepath = os.path.join(docs_dir, filename)

    # PDF作成
    doc = SimpleDocTemplate(
        filepath,
        pagesize=A4,
        leftMargin=20*mm,
        rightMargin=20*mm,
        topMargin=20*mm,
        bottomMargin=20*mm
    )

    # 日本語フォント設定を試みる
    try:
        # Windows標準フォント
        font_paths = [
            "C:/Windows/Fonts/msgothic.ttc",  # MSゴシック
            "C:/Windows/Fonts/meiryo.ttc",     # メイリオ
            "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",  # Mac
            "/usr/share/fonts/truetype/takao-gothic/TakaoPGothic.ttf",  # Linux
        ]

        font_registered = False
        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    pdfmetrics.registerFont(TTFont('JapaneseFont', font_path))
                    font_registered = True
                    break
                except:
                    continue

        if font_registered:
            font_name = 'JapaneseFont'
        else:
            # フォールバック: Helvetica（日本語は文字化けする可能性あり）
            font_name = 'Helvetica'
            print("⚠️ Warning: Japanese font not found. Using Helvetica as fallback.")
    except Exception as e:
        font_name = 'Helvetica'
        print(f"⚠️ Warning: Could not register Japanese font: {e}")

    # スタイル設定
    styles = getSampleStyleSheet()

    # タイトルスタイル
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontName=font_name,
        fontSize=16,
        alignment=TA_CENTER,
        spaceAfter=12,
    )

    # 本文スタイル
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['BodyText'],
        fontName=font_name,
        fontSize=10,
        leading=14,
        alignment=TA_LEFT,
        spaceAfter=6,
    )

    # コンテンツを構築
    story = []

    # タイトル追加
    story.append(Paragraph(title, title_style))
    story.append(Spacer(1, 10*mm))

    # 本文を段落ごとに分割してPDFに追加
    paragraphs = content.split('\n')
    for para in paragraphs:
        if para.strip():
            # HTMLエスケープ処理
            para_escaped = para.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            story.append(Paragraph(para_escaped, body_style))
        else:
            # 空行はスペーサーとして追加
            story.append(Spacer(1, 3*mm))

    # PDF生成
    doc.build(story)

    return filepath


@tool
def generate_document(
    content: str,
    title: str,
    document_type: str = "general"
) -> str:
    """任意の文書内容をPDF形式で生成します。

    このツールはテンプレートを使用せず、LLMが作成した完成済みの文書内容を
    そのままPDF化します。長文ドキュメントの生成に適しています。

    Args:
        content: PDF化する文書の完成済み内容（長文推奨）
            LLMが作成した文書の本文をそのまま渡してください。
            改行は段落の区切りとして解釈されます。
        title: 文書のタイトル（PDFの表紙に表示されます）
        document_type: 文書の種別（ファイル名の接頭辞として使用）
            例: "report", "proposal", "analysis", "summary", "document" など

    Returns:
        str: 生成されたPDFファイルのパスと確認メッセージ

    使用例:
    ```python
    # LLMが作成した長文レポートをPDF化
    generate_document(
        content="第1章 はじめに\n\n本報告書では...(長文が続く)",
        title="市場調査報告書",
        document_type="report"
    )

    # 提案書をPDF化
    generate_document(
        content="ご提案内容\n\n貴社における...(提案内容)",
        title="システム導入提案書",
        document_type="proposal"
    )
    ```

    注意:
    - reportlab がインストールされている必要があります
    - 日本語フォントは自動検出されます（Windows/Mac/Linux対応）
    - 長文ドキュメントの生成を想定しています
    """
    try:
        print(f"\n{'='*60}")
        print(f"📄 [generate_document] PDF生成開始")
        print(f"   タイトル: {title}")
        print(f"   文書種別: {document_type}")
        print(f"   文字数: {len(content)}文字")
        print(f"{'='*60}\n")

        if not content or not content.strip():
            return "❌ エラー: 文書内容（content）が空です。PDF化する内容を指定してください。"

        if not title or not title.strip():
            return "❌ エラー: タイトル（title）が空です。文書のタイトルを指定してください。"

        # PDFとして保存
        filepath = _save_as_pdf(content, title, document_type)

        # 文字数情報
        char_count = len(content)
        line_count = content.count('\n') + 1

        # ファイルサイズを取得
        file_size = os.path.getsize(filepath)
        filename = os.path.basename(filepath)

        print(f"✅ PDF生成成功: {filepath}")
        print(f"   ファイルサイズ: {file_size} bytes")

        # グローバルリストにパスを追加（バックエンドから参照可能）
        global LAST_GENERATED_PDFS
        LAST_GENERATED_PDFS.append(filepath)
        print(f"   グローバルリストに追加: {filepath}")

        # ファイルパスをタグで返す（バックエンドがBase64変換してフロントエンドに送信）
        return f"""✅ PDFを生成しました

**タイトル**: {title}
**文書種別**: {document_type}
**文字数**: {char_count}文字
**行数**: {line_count}行
**ファイルサイズ**: {file_size:,} bytes

[PDF_FILE]{filename}[/PDF_FILE]

PDFファイルが正常に生成されました。ダウンロードボタンからダウンロードできます。"""

    except ImportError as e:
        print(f"❌ エラー: {str(e)}")
        return f"""❌ エラー: reportlab がインストールされていません

PDFを生成するには以下のコマンドを実行してください:
```
pip install reportlab
```

エラー詳細: {str(e)}"""

    except Exception as e:
        print(f"❌ エラー: {str(e)}")
        import traceback
        traceback.print_exc()
        return f"❌ PDF生成中にエラーが発生しました: {str(e)}"

