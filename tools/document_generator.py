"""プロフェッショナルPDF生成ツール（generate_document）

ビジネス文書として使用可能な高品質なPDFを生成します。
ヘッダー・フッター、表組み、箇条書き、セクション区切り等をサポート。
"""
import os
import re
import uuid
from datetime import datetime
from typing import Optional, List, Tuple
from strands import tool

# 最後に生成されたPDFファイルのパスを保存（バックエンドから参照）
LAST_GENERATED_PDFS: List[str] = []

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
        KeepTogether, PageTemplate, Frame, BaseDocTemplate
    )
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    print("⚠️ Warning: reportlab not installed. PDF generation will be disabled.")


class BusinessDocTemplate(BaseDocTemplate):
    """ビジネス文書用のカスタムテンプレート（ヘッダー・フッター付き）"""

    def __init__(self, filename, **kw):
        self.allowSplitting = 0
        BaseDocTemplate.__init__(self, filename, **kw)

        # ページテンプレート設定
        frame = Frame(
            self.leftMargin, self.bottomMargin,
            self.width, self.height,
            id='normal'
        )

        template = PageTemplate(id='business', frames=frame, onPage=self._header_footer)
        self.addPageTemplates([template])

        # ドキュメント情報（後で設定）
        self.doc_title = kw.get('title', '')
        self.doc_type = kw.get('doc_type', '')
        self.company_name = kw.get('company_name', '')

    def _header_footer(self, canvas, doc):
        """各ページにヘッダーとフッターを追加"""
        canvas.saveState()

        # ページサイズ
        page_width = A4[0]
        page_height = A4[1]

        # ヘッダー（上部の線）
        canvas.setStrokeColor(colors.HexColor('#2C3E50'))
        canvas.setLineWidth(2)
        canvas.line(20*mm, page_height - 15*mm, page_width - 20*mm, page_height - 15*mm)

        # ヘッダーテキスト（会社名）
        if self.company_name:
            canvas.setFont('JapaneseFont', 9)
            canvas.setFillColor(colors.HexColor('#34495E'))
            canvas.drawString(22*mm, page_height - 12*mm, self.company_name)

        # フッター（下部の線）
        canvas.setStrokeColor(colors.HexColor('#2C3E50'))
        canvas.setLineWidth(0.5)
        canvas.line(20*mm, 15*mm, page_width - 20*mm, 15*mm)

        # ページ番号
        canvas.setFont('JapaneseFont', 9)
        canvas.setFillColor(colors.HexColor('#7F8C8D'))
        page_num = f"- {doc.page} -"
        canvas.drawCentredString(page_width / 2, 10*mm, page_num)

        # 作成日時（右下）
        created_date = datetime.now().strftime('%Y年%m月%d日')
        canvas.drawRightString(page_width - 22*mm, 10*mm, f"作成日: {created_date}")

        canvas.restoreState()


def _register_japanese_font() -> str:
    """日本語フォントを登録"""
    font_paths = [
        "C:/Windows/Fonts/msgothic.ttc",  # MSゴシック
        "C:/Windows/Fonts/meiryo.ttc",     # メイリオ
        "C:/Windows/Fonts/yugothic.ttf",   # 游ゴシック
        "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",  # Mac
        "/usr/share/fonts/truetype/takao-gothic/TakaoPGothic.ttf",  # Linux
    ]

    for font_path in font_paths:
        if os.path.exists(font_path):
            try:
                pdfmetrics.registerFont(TTFont('JapaneseFont', font_path))
                return 'JapaneseFont'
            except:
                continue

    # フォールバック
    print("⚠️ Warning: Japanese font not found. Using Helvetica as fallback.")
    return 'Helvetica'


def _create_styles(font_name: str) -> dict:
    """プロフェッショナルなスタイルセットを作成"""
    styles = {}

    # タイトルスタイル（大見出し）
    styles['Title'] = ParagraphStyle(
        'Title',
        fontName=font_name,
        fontSize=18,
        leading=24,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#2C3E50'),
        spaceAfter=15,
        spaceBefore=10,
    )

    # 見出し1（セクションタイトル）
    styles['Heading1'] = ParagraphStyle(
        'Heading1',
        fontName=font_name,
        fontSize=14,
        leading=18,
        textColor=colors.HexColor('#34495E'),
        spaceAfter=8,
        spaceBefore=12,
        borderWidth=0,
        borderPadding=4,
        borderColor=colors.HexColor('#3498DB'),
        borderRadius=None,
        leftIndent=0,
        backColor=colors.HexColor('#ECF0F1'),
    )

    # 見出し2（サブセクション）
    styles['Heading2'] = ParagraphStyle(
        'Heading2',
        fontName=font_name,
        fontSize=12,
        leading=16,
        textColor=colors.HexColor('#2C3E50'),
        spaceAfter=6,
        spaceBefore=10,
        leftIndent=5,
    )

    # 本文（通常）
    styles['Body'] = ParagraphStyle(
        'Body',
        fontName=font_name,
        fontSize=10,
        leading=16,
        alignment=TA_LEFT,
        textColor=colors.HexColor('#2C3E50'),
        spaceAfter=4,
    )

    # 本文（両端揃え）
    styles['BodyJustify'] = ParagraphStyle(
        'BodyJustify',
        parent=styles['Body'],
        alignment=TA_JUSTIFY,
    )

    # 箇条書き
    styles['Bullet'] = ParagraphStyle(
        'Bullet',
        fontName=font_name,
        fontSize=10,
        leading=16,
        leftIndent=15,
        bulletIndent=5,
        textColor=colors.HexColor('#2C3E50'),
        spaceAfter=3,
    )

    # 重要事項（強調）
    styles['Important'] = ParagraphStyle(
        'Important',
        fontName=font_name,
        fontSize=10,
        leading=16,
        textColor=colors.HexColor('#C0392B'),
        backColor=colors.HexColor('#FADBD8'),
        borderWidth=1,
        borderColor=colors.HexColor('#E74C3C'),
        borderPadding=5,
        spaceAfter=8,
        spaceBefore=8,
    )

    # 注釈・補足
    styles['Note'] = ParagraphStyle(
        'Note',
        fontName=font_name,
        fontSize=9,
        leading=14,
        textColor=colors.HexColor('#7F8C8D'),
        leftIndent=10,
        spaceAfter=4,
    )

    return styles


def _clean_markdown(text: str) -> str:
    """Markdown記法をPDF向けにクリーンアップ"""
    # 太字記法を除去（**text** → text）
    text = re.sub(r'\*\*\*\*', '', text)  # **** の空パターンを除去
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)  # **text** → text
    text = re.sub(r'\*(.+?)\*', r'\1', text)  # *text* → text
    
    # 見出し記号を除去（行頭の # を除去）
    text = re.sub(r'^#{1,6}\s*', '', text)
    
    # 下線を除去
    text = re.sub(r'__(.+?)__', r'\1', text)
    
    # 取り消し線を除去
    text = re.sub(r'~~(.+?)~~', r'\1', text)
    
    # コードブロック記号を除去
    text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
    text = re.sub(r'`(.+?)`', r'\1', text)
    
    # 絵文字風の記号を除去（オプション）
    # text = re.sub(r'[📊💰📄🎭✅❌⚠️📝🎯💡]', '', text)
    
    return text.strip()


def _parse_markdown_structure(content: str) -> List[Tuple[str, str]]:
    """マークダウン形式の文書を解析して構造化"""
    lines = content.split('\n')
    structured_content = []

    for line in lines:
        line = line.rstrip()

        # 空行
        if not line:
            structured_content.append(('spacer', ''))
            continue

        # 見出し1 (# または ## )
        if re.match(r'^#{1,2}\s+', line):
            heading_text = re.sub(r'^#{1,2}\s+', '', line).strip()
            heading_text = _clean_markdown(heading_text)
            structured_content.append(('heading1', heading_text))
        # 見出し2 (### または ####)
        elif re.match(r'^#{3,4}\s+', line):
            heading_text = re.sub(r'^#{3,4}\s+', '', line).strip()
            heading_text = _clean_markdown(heading_text)
            structured_content.append(('heading2', heading_text))
        # 見出し3以下 (##### 以上) → 本文として扱う
        elif re.match(r'^#{5,}\s+', line):
            body_text = re.sub(r'^#{5,}\s+', '', line).strip()
            body_text = _clean_markdown(body_text)
            structured_content.append(('body', body_text))
        # 箇条書き (- または * )
        elif line.strip().startswith('- ') or line.strip().startswith('* '):
            bullet_text = line.strip()[2:].strip()
            bullet_text = _clean_markdown(bullet_text)
            structured_content.append(('bullet', bullet_text))
        # 重要事項（【重要】で始まる行）
        elif '【重要】' in line or '**重要**' in line:
            important_text = _clean_markdown(line)
            structured_content.append(('important', important_text))
        # 注釈（※で始まる行）
        elif line.strip().startswith('※'):
            note_text = _clean_markdown(line)
            structured_content.append(('note', note_text))
        # 表の検出（|で始まる行）
        elif '|' in line and line.count('|') >= 2:
            # セパレータ行（---）をスキップ
            if re.match(r'^[\|\s\-:]+$', line):
                continue
            table_text = _clean_markdown(line)
            structured_content.append(('table_row', table_text))
        # 通常の本文
        else:
            body_text = _clean_markdown(line)
            if body_text:  # 空でない場合のみ追加
                structured_content.append(('body', body_text))

    return structured_content


def _create_table_from_rows(table_rows: List[str], styles: dict) -> Table:
    """表データを作成"""
    # 表データを解析
    data = []
    for row in table_rows:
        cells = [cell.strip() for cell in row.split('|') if cell.strip()]
        data.append(cells)

    if not data:
        return None

    # テーブルスタイル
    table_style = TableStyle([
        # ヘッダー行（1行目）
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498DB')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'JapaneseFont'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),

        # データ行（2行目以降）
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#2C3E50')),
        ('FONTNAME', (0, 1), (-1, -1), 'JapaneseFont'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('TOPPADDING', (0, 1), (-1, -1), 6),

        # 全体
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#BDC3C7')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),

        # 行の交互色
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8F9FA')]),
    ])

    table = Table(data, style=table_style, hAlign='LEFT')
    return table


def _build_pdf_content(content: str, title: str, styles: dict) -> List:
    """構造化されたPDFコンテンツを構築"""
    story = []

    # タイトル
    story.append(Paragraph(title, styles['Title']))
    story.append(Spacer(1, 8*mm))

    # 文書内容を構造化解析
    structured = _parse_markdown_structure(content)

    # 表データの一時保存
    table_buffer = []

    for i, (elem_type, text) in enumerate(structured):
        # 表の処理（連続する表行をまとめる）
        if elem_type == 'table_row':
            table_buffer.append(text)
            # 次の要素が表でない場合、または最後の要素の場合
            if i == len(structured) - 1 or structured[i+1][0] != 'table_row':
                if table_buffer:
                    # ヘッダー区切り行（---）を除外
                    filtered_rows = [row for row in table_buffer if not re.match(r'^[\|\s\-:]+$', row)]
                    if filtered_rows:
                        table = _create_table_from_rows(filtered_rows, styles)
                        if table:
                            story.append(table)
                            story.append(Spacer(1, 5*mm))
                    table_buffer = []
            continue

        # 他の要素タイプの処理
        if elem_type == 'spacer':
            story.append(Spacer(1, 3*mm))

        elif elem_type == 'heading1':
            story.append(Spacer(1, 4*mm))
            story.append(Paragraph(f"<b>{_escape_html(text)}</b>", styles['Heading1']))

        elif elem_type == 'heading2':
            story.append(Paragraph(f"<b>{_escape_html(text)}</b>", styles['Heading2']))

        elif elem_type == 'bullet':
            bullet_para = Paragraph(f"• {_escape_html(text)}", styles['Bullet'])
            story.append(bullet_para)

        elif elem_type == 'important':
            story.append(Paragraph(f"<b>{_escape_html(text)}</b>", styles['Important']))

        elif elem_type == 'note':
            story.append(Paragraph(_escape_html(text), styles['Note']))

        elif elem_type == 'body':
            # Markdown記法は既に_clean_markdownで除去済み
            story.append(Paragraph(_escape_html(text), styles['BodyJustify']))

    return story


def _escape_html(text: str) -> str:
    """HTML特殊文字をエスケープ（ただし<b>タグは保持）"""
    # <b>タグを一時的に保護
    text = text.replace('<b>', '<<<B>>>')
    text = text.replace('</b>', '<<</B>>>')

    # エスケープ
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')

    # <b>タグを復元
    text = text.replace('<<<B>>>', '<b>')
    text = text.replace('<<</B>>>', '</b>')

    return text


def _save_as_professional_pdf(
    content: str,
    title: str,
    document_type: str,
    company_name: str = ""
) -> str:
    """プロフェッショナルなPDFとして保存"""
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

    # 日本語フォント登録
    font_name = _register_japanese_font()

    # スタイル作成
    styles = _create_styles(font_name)

    # カスタムテンプレートを使用してPDF作成
    doc = BusinessDocTemplate(
        filepath,
        pagesize=A4,
        leftMargin=20*mm,
        rightMargin=20*mm,
        topMargin=25*mm,
        bottomMargin=20*mm,
        title=title,
        doc_type=document_type,
        company_name=company_name
    )

    # コンテンツを構築
    story = _build_pdf_content(content, title, styles)

    # PDF生成
    doc.build(story)

    return filepath


@tool
def generate_document(
    content: str,
    title: str,
    document_type: str = "general",
    company_name: str = ""
) -> str:
    """ビジネス文書として使用可能な高品質PDFを生成します。

    ヘッダー・フッター、表組み、箇条書き、セクション区切り等をサポート。
    マークダウン形式の記法に対応しています。

    Args:
        content: PDF化する文書の完成済み内容（マークダウン記法対応）
            以下の記法をサポート:
            - ## 見出し1（セクションタイトル）
            - ### 見出し2（サブセクション）
            - - 箇条書き（または * ）
            - **太字**（強調）
            - 【重要】で始まる行（重要事項として強調表示）
            - ※で始まる行（注釈として小さく表示）
            - | 列1 | 列2 | 形式の表組み
        title: 文書のタイトル（PDFの表紙に大きく表示されます）
        document_type: 文書の種別（ファイル名の接頭辞として使用）
            例: "proposal", "quotation", "request_letter", "analysis", "report" など
        company_name: 会社名（ヘッダーに表示されます、省略可能）

    Returns:
        str: 生成されたPDFファイルのパスと確認メッセージ

    使用例:
    ```python
    # 価格改定申入書をPDF化
    generate_document(
        content='''
        ## 価格改定のお願い

        拝啓 時下ますますご清栄のこととお慶び申し上げます。

        ### 改定の背景

        - 原材料費の高騰（前年比+20%）
        - 労務費の上昇（最低賃金改定）
        - エネルギー費の増加（+30%）

        【重要】現在の価格では採算が取れない状況となっております。

        ### 改定内容

        | 項目 | 現行価格 | 改定後価格 | 増加率 |
        | 製品A | 10,000円 | 11,000円 | +10% |
        | 製品B | 15,000円 | 16,500円 | +10% |

        ※ 改定実施日: 2025年4月1日
        ''',
        title="価格改定申入書",
        document_type="request_letter",
        company_name="株式会社サンプル"
    )
    ```

    注意:
    - reportlab がインストールされている必要があります
    - 日本語フォントは自動検出されます（Windows/Mac/Linux対応）
    - ヘッダー・フッターに作成日とページ番号が自動付与されます
    """
    try:
        print(f"\n{'='*60}")
        print(f"📄 [generate_document] プロフェッショナルPDF生成開始")
        print(f"   タイトル: {title}")
        print(f"   文書種別: {document_type}")
        print(f"   会社名: {company_name or '(未指定)'}")
        print(f"   文字数: {len(content)}文字")
        print(f"{'='*60}\n")

        if not content or not content.strip():
            return "❌ エラー: 文書内容（content）が空です。PDF化する内容を指定してください。"

        if not title or not title.strip():
            return "❌ エラー: タイトル（title）が空です。文書のタイトルを指定してください。"

        # プロフェッショナルPDFとして保存
        filepath = _save_as_professional_pdf(content, title, document_type, company_name)

        # 文字数情報
        char_count = len(content)
        line_count = content.count('\n') + 1

        # ファイルサイズを取得
        file_size = os.path.getsize(filepath)
        filename = os.path.basename(filepath)

        print(f"✅ プロフェッショナルPDF生成成功: {filepath}")
        print(f"   ファイルサイズ: {file_size} bytes")

        # グローバルリストにパスを追加（バックエンドから参照可能）
        global LAST_GENERATED_PDFS
        LAST_GENERATED_PDFS.append(filepath)
        print(f"   グローバルリストに追加: {filepath}")

        # ファイルパスをタグで返す（バックエンドがBase64変換してフロントエンドに送信）
        return f"""✅ ビジネス文書PDFを生成しました

**タイトル**: {title}
**文書種別**: {document_type}
**会社名**: {company_name or '(未指定)'}
**文字数**: {char_count}文字
**行数**: {line_count}行
**ファイルサイズ**: {file_size:,} bytes

**デザイン特徴**:
- ヘッダー・フッター付き（ページ番号・作成日自動付与）
- 見出し階層のスタイリング
- 表組み対応
- 箇条書きの視覚的表現
- ビジネス文書として使用可能な品質

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
