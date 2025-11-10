"""
図生成機能の動作確認テスト
"""
import sys
import io
sys.path.insert(0, 'C:\\Users\\Rikuto\\SME-Agency-Price-Transfer-Support-AI')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app import DiagramGenerator, _generate_bar_chart_code, _generate_flowchart_code
import os

def test_bar_chart():
    """棒グラフ生成テスト"""
    print("=" * 50)
    print("テスト1: 棒グラフ生成")
    print("=" * 50)

    code = _generate_bar_chart_code("売上実績", "四半期別の売上実績")
    success, image_path, error = DiagramGenerator.generate(code, timeout=30)

    if success:
        print(f"✅ 成功: {image_path}")
        if os.path.exists(image_path):
            print(f"✅ ファイル存在確認: {os.path.getsize(image_path)} bytes")
        return True
    else:
        print(f"❌ 失敗: {error}")
        return False

def test_flowchart():
    """フローチャート生成テスト"""
    print("\n" + "=" * 50)
    print("テスト2: フローチャート生成")
    print("=" * 50)

    code = _generate_flowchart_code("プロセスフロー", "業務プロセス")
    success, image_path, error = DiagramGenerator.generate(code, timeout=30)

    if success:
        print(f"✅ 成功: {image_path}")
        if os.path.exists(image_path):
            print(f"✅ ファイル存在確認: {os.path.getsize(image_path)} bytes")
        return True
    else:
        print(f"❌ 失敗: {error}")
        return False

if __name__ == "__main__":
    try:
        test1 = test_bar_chart()
        test2 = test_flowchart()

        print("\n" + "=" * 50)
        print("テスト結果サマリー")
        print("=" * 50)
        print(f"棒グラフ: {'✅ PASS' if test1 else '❌ FAIL'}")
        print(f"フローチャート: {'✅ PASS' if test2 else '❌ FAIL'}")

        if test1 and test2:
            print("\n🎉 すべてのテストが成功しました！")
        else:
            print("\n⚠️ 一部のテストが失敗しました")

    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
