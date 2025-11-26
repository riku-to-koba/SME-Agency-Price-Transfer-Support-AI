/**
 * ツールモーダルの設定ファイル
 * 
 * 新しいモーダルを追加する場合:
 * 1. ModalType に新しい種別を追加
 * 2. MODAL_CONFIGS に設定を追加
 * 3. バックエンドに対応するエンドポイントを追加
 */

// モーダル種別の定義
export type ModalType = 
  | 'ideal_pricing'      // 理想の原価計算用（松竹梅プラン）
  | 'cost_comparison'    // 価格転嫁検討用（既存）
  // 将来の拡張用
  // | 'should_transfer'  // 価格転嫁すべきか判定用
  // | 'breakeven_analysis' // 損益分岐点分析用

// フィールドの型
export type FieldType = 'number' | 'text' | 'select' | 'percentage'

// フィールド定義
export interface FieldConfig {
  id: string
  label: string
  type: FieldType
  placeholder?: string
  required?: boolean
  suffix?: string  // 単位（円、%など）
  defaultValue?: string | number
  options?: { value: string; label: string }[]  // select用
  group?: string  // グループ分け用
}

// モーダル設定
export interface ModalConfig {
  type: ModalType
  title: string
  description: string
  fields: FieldConfig[]
  submitLabel: string
  apiEndpoint: string
  // フィールドのグループ定義（セクション分け用）
  groups?: { id: string; title: string }[]
}

// ================================
// モーダル設定の定義
// ================================

export const MODAL_CONFIGS: Record<ModalType, ModalConfig> = {
  // 理想の原価計算用モーダル
  ideal_pricing: {
    type: 'ideal_pricing',
    title: '理想の原価計算',
    description: '現在の原価構造と価格上昇率を入力して、適正価格（松竹梅プラン）を算出します。',
    submitLabel: '試算する',
    apiEndpoint: '/api/ideal-pricing',
    groups: [
      { id: 'cost_structure', title: '現在の原価構造' },
      { id: 'price_changes', title: '価格上昇率' },
      { id: 'optional', title: 'オプション' },
    ],
    fields: [
      // 原価構造
      {
        id: 'material_cost',
        label: '材料費',
        type: 'number',
        placeholder: '例: 1000000',
        required: true,
        suffix: '円',
        group: 'cost_structure',
      },
      {
        id: 'labor_cost',
        label: '労務費',
        type: 'number',
        placeholder: '例: 875000',
        required: true,
        suffix: '円',
        group: 'cost_structure',
      },
      {
        id: 'energy_cost',
        label: 'エネルギー費',
        type: 'number',
        placeholder: '例: 250000',
        required: true,
        suffix: '円',
        group: 'cost_structure',
      },
      {
        id: 'overhead',
        label: 'その他経費',
        type: 'number',
        placeholder: '例: 375000',
        required: true,
        suffix: '円',
        group: 'cost_structure',
      },
      // 価格上昇率
      {
        id: 'material_cost_change',
        label: '材料費の上昇率',
        type: 'percentage',
        placeholder: '例: 20',
        required: true,
        suffix: '%',
        group: 'price_changes',
      },
      {
        id: 'labor_cost_change',
        label: '労務費の上昇率',
        type: 'percentage',
        placeholder: '例: 5',
        required: true,
        suffix: '%',
        group: 'price_changes',
      },
      {
        id: 'energy_cost_change',
        label: 'エネルギー費の上昇率',
        type: 'percentage',
        placeholder: '例: 30',
        required: true,
        suffix: '%',
        group: 'price_changes',
      },
      // オプション
      {
        id: 'current_sales',
        label: '現在の売上高',
        type: 'number',
        placeholder: '例: 3000000（未入力の場合は推計）',
        required: false,
        suffix: '円',
        group: 'optional',
      },
    ],
  },

  // 価格転嫁検討用モーダル（既存の機能を設定化）
  cost_comparison: {
    type: 'cost_comparison',
    title: '価格転嫁検討ツール',
    description: 'コスト高騰前と現在のデータを入力して、価格転嫁の必要性を分析します。',
    submitLabel: '分析実行',
    apiEndpoint: '/api/cost-analysis',
    groups: [
      { id: 'before', title: 'コスト高騰前の情報' },
      { id: 'current', title: '現在の情報' },
    ],
    fields: [
      // コスト高騰前
      {
        id: 'before_sales',
        label: '売上高',
        type: 'number',
        placeholder: '例: 10000000',
        required: true,
        suffix: '円',
        group: 'before',
      },
      {
        id: 'before_cost',
        label: '売上原価',
        type: 'number',
        placeholder: '例: 6000000',
        required: true,
        suffix: '円',
        group: 'before',
      },
      {
        id: 'before_expenses',
        label: '販管費・その他経費',
        type: 'number',
        placeholder: '例: 2000000',
        required: true,
        suffix: '円',
        group: 'before',
      },
      // 現在
      {
        id: 'current_sales',
        label: '売上高',
        type: 'number',
        placeholder: '例: 10000000',
        required: true,
        suffix: '円',
        group: 'current',
      },
      {
        id: 'current_cost',
        label: '売上原価',
        type: 'number',
        placeholder: '例: 7000000',
        required: true,
        suffix: '円',
        group: 'current',
      },
      {
        id: 'current_expenses',
        label: '販管費・その他経費',
        type: 'number',
        placeholder: '例: 2000000',
        required: true,
        suffix: '円',
        group: 'current',
      },
    ],
  },
}

// ツール名からモーダル種別へのマッピング
export const TOOL_TO_MODAL_MAP: Record<string, ModalType> = {
  'calculate_cost_impact': 'ideal_pricing',
  'analyze_cost_impact': 'cost_comparison',  // 後方互換性
}

// モーダル種別からツール名へのマッピング（逆引き）
export const MODAL_TO_TOOL_MAP: Record<ModalType, string> = {
  'ideal_pricing': 'calculate_cost_impact',
  'cost_comparison': 'analyze_cost_impact',
}



