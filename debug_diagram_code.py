"""デバッグ: 生成されるPythonコードを確認"""
import sys
sys.path.insert(0, 'C:\\Users\\Rikuto\\SME-Agency-Price-Transfer-Support-AI')

from app import DiagramGenerator, _generate_bar_chart_code

# バーチャートコード生成
user_code = _generate_bar_chart_code("テスト棒グラフ", "説明")
print("=" * 50)
print("ユーザー生成コード:")
print("=" * 50)
print(user_code[:500])

# ラップ後のコード
wrapped = DiagramGenerator._create_python_code_wrapper(user_code, "C:\\temp\\test.png")
print("\n" + "=" * 50)
print("ラップ後のコード（最初の1500文字）:")
print("=" * 50)
print(wrapped[:1500])
