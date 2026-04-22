import React, { useState, useEffect } from 'react';
import {
  getFieldSchemas,
  createFieldSchema,
  updateFieldSchema,
  deleteFieldSchema,
  type FieldSchema,
  type FieldSchemaCreate,
  type FieldSuggestion,
} from '../../services/api';

interface FieldSchemaManagerProps {
  categoryId: number;
}

const FIELD_TYPES = [
  { value: 'text', label: 'テキスト' },
  { value: 'number', label: '数値' },
  { value: 'currency', label: '通貨' },
  { value: 'percentage', label: 'パーセンテージ' },
  { value: 'date', label: '日付' },
  { value: 'boolean', label: '真偽値' },
  { value: 'list', label: 'リスト' },
] as const;

const FieldSchemaManager: React.FC<FieldSchemaManagerProps> = ({ categoryId }) => {
  const [schemas, setSchemas] = useState<FieldSchema[]>([]);
  const [suggestions, setSuggestions] = useState<FieldSuggestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);

  // Form state
  const [formData, setFormData] = useState<FieldSchemaCreate>({
    category_id: categoryId,
    field_name: '',
    field_type: 'text',
    is_required: false,
    validation_rules: undefined,
    display_order: 0,
  });

  // Validation rules state
  const [validationRules, setValidationRules] = useState<{
    min?: number;
    max?: number;
    pattern?: string;
    options?: string;
    max_length?: number;
    currency_code?: string;
    format?: string;
  }>({});

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    loadSchemas();
  }, [categoryId]);

  const loadSchemas = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getFieldSchemas(categoryId);
      setSchemas(data.sort((a, b) => a.display_order - b.display_order));
    } catch (err) {
      setError('フィールドスキーマの読み込みに失敗しました');
      console.error('Failed to load field schemas:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    try {
      setError(null);
      
      // Build validation rules based on field type
      const rules = buildValidationRules(formData.field_type, validationRules);
      
      const dataToSubmit = {
        ...formData,
        validation_rules: Object.keys(rules).length > 0 ? rules : undefined,
      };

      if (editingId !== null) {
        // Update existing schema
        await updateFieldSchema(editingId, dataToSubmit);
      } else {
        // Create new schema
        await createFieldSchema(dataToSubmit);
      }

      // Reset form
      resetForm();

      // Reload schemas
      await loadSchemas();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { status?: number } };
      if (axiosErr.response?.status === 409) {
        setError('同一カテゴリ内に同名のフィールドが既に存在します');
      } else if (axiosErr.response?.status === 422) {
        setError('サポートされていないフィールド型です');
      } else {
        setError('フィールドスキーマの保存に失敗しました');
      }
      console.error('Failed to save field schema:', err);
    }
  };

  const buildValidationRules = (fieldType: string, rules: typeof validationRules): Record<string, string | number | string[]> => {
    const result: Record<string, string | number | string[]> = {};
    
    switch (fieldType) {
      case 'text':
        if (rules.pattern) result.pattern = rules.pattern;
        if (rules.max_length) result.max_length = rules.max_length;
        break;
      case 'number':
        if (rules.min !== undefined) result.min = rules.min;
        if (rules.max !== undefined) result.max = rules.max;
        break;
      case 'currency':
        if (rules.min !== undefined) result.min = rules.min;
        if (rules.currency_code) result.currency_code = rules.currency_code;
        break;
      case 'percentage':
        if (rules.min !== undefined) result.min = rules.min;
        if (rules.max !== undefined) result.max = rules.max;
        break;
      case 'date':
        if (rules.format) result.format = rules.format;
        break;
      case 'list':
        if (rules.options) {
          result.options = rules.options.split(',').map((opt: string) => opt.trim()).filter(Boolean);
        }
        break;
    }
    
    return result;
  };

  const handleEdit = (schema: FieldSchema) => {
    setEditingId(schema.id);
    setFormData({
      category_id: categoryId,
      field_name: schema.field_name,
      field_type: schema.field_type,
      is_required: schema.is_required,
      validation_rules: schema.validation_rules || undefined,
      display_order: schema.display_order,
    });
    
    // Parse validation rules for form
    if (schema.validation_rules) {
      const rules: typeof validationRules = {};
      const vr = schema.validation_rules as Record<string, unknown>;
      
      if (vr.min !== undefined) rules.min = Number(vr.min);
      if (vr.max !== undefined) rules.max = Number(vr.max);
      if (vr.pattern) rules.pattern = String(vr.pattern);
      if (vr.max_length) rules.max_length = Number(vr.max_length);
      if (vr.currency_code) rules.currency_code = String(vr.currency_code);
      if (vr.format) rules.format = String(vr.format);
      if (vr.options && Array.isArray(vr.options)) {
        rules.options = (vr.options as string[]).join(', ');
      }
      
      setValidationRules(rules);
    } else {
      setValidationRules({});
    }
    
    setShowAddForm(true);
  };

  const resetForm = () => {
    setEditingId(null);
    setFormData({
      category_id: categoryId,
      field_name: '',
      field_type: 'text',
      is_required: false,
      validation_rules: undefined,
      display_order: schemas.length,
    });
    setValidationRules({});
    setShowAddForm(false);
    setError(null);
  };

  const handleDelete = async (id: number) => {
    try {
      setError(null);
      await deleteFieldSchema(id);
      setDeleteConfirm(null);
      await loadSchemas();
    } catch (err) {
      setError('フィールドスキーマの削除に失敗しました');
      console.error('Failed to delete field schema:', err);
    }
  };

  const handleApproveSuggestion = async (suggestion: FieldSuggestion) => {
    try {
      setError(null);
      
      const newSchema: FieldSchemaCreate = {
        category_id: categoryId,
        field_name: suggestion.field_name,
        field_type: suggestion.field_type,
        is_required: false,
        validation_rules: undefined,
        display_order: schemas.length,
      };
      
      await createFieldSchema(newSchema);
      
      // Remove from suggestions
      setSuggestions(suggestions.filter(s => s.field_name !== suggestion.field_name));
      
      // Reload schemas
      await loadSchemas();
    } catch (err: any) {
      if (err.response?.status === 409) {
        setError('同一カテゴリ内に同名のフィールドが既に存在します');
      } else {
        setError('フィールド候補の承認に失敗しました');
      }
      console.error('Failed to approve field suggestion:', err);
    }
  };

  const renderValidationRulesForm = () => {
    const fieldType = formData.field_type;
    
    return (
      <div className="space-y-3">
        <h4 className="text-sm font-medium text-gray-700">バリデーションルール</h4>
        
        {(fieldType === 'text') && (
          <>
            <div>
              <label className="block text-sm text-gray-600 mb-1">正規表現パターン</label>
              <input
                type="text"
                value={validationRules.pattern || ''}
                onChange={(e) => setValidationRules({ ...validationRules, pattern: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="例: ^[A-Z].*"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">最大文字数</label>
              <input
                type="number"
                value={validationRules.max_length || ''}
                onChange={(e) => setValidationRules({ ...validationRules, max_length: e.target.value ? parseInt(e.target.value) : undefined })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                min="1"
              />
            </div>
          </>
        )}
        
        {(fieldType === 'number' || fieldType === 'percentage') && (
          <>
            <div>
              <label className="block text-sm text-gray-600 mb-1">最小値</label>
              <input
                type="number"
                value={validationRules.min ?? ''}
                onChange={(e) => setValidationRules({ ...validationRules, min: e.target.value ? parseFloat(e.target.value) : undefined })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                step="any"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">最大値</label>
              <input
                type="number"
                value={validationRules.max ?? ''}
                onChange={(e) => setValidationRules({ ...validationRules, max: e.target.value ? parseFloat(e.target.value) : undefined })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                step="any"
              />
            </div>
          </>
        )}
        
        {fieldType === 'currency' && (
          <>
            <div>
              <label className="block text-sm text-gray-600 mb-1">最小値</label>
              <input
                type="number"
                value={validationRules.min ?? ''}
                onChange={(e) => setValidationRules({ ...validationRules, min: e.target.value ? parseFloat(e.target.value) : undefined })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                step="any"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">通貨コード</label>
              <input
                type="text"
                value={validationRules.currency_code || ''}
                onChange={(e) => setValidationRules({ ...validationRules, currency_code: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="例: JPY, USD"
              />
            </div>
          </>
        )}
        
        {fieldType === 'date' && (
          <div>
            <label className="block text-sm text-gray-600 mb-1">日付フォーマット</label>
            <input
              type="text"
              value={validationRules.format || ''}
              onChange={(e) => setValidationRules({ ...validationRules, format: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="例: YYYY-MM-DD"
            />
          </div>
        )}
        
        {fieldType === 'list' && (
          <div>
            <label className="block text-sm text-gray-600 mb-1">選択肢（カンマ区切り）</label>
            <input
              type="text"
              value={validationRules.options || ''}
              onChange={(e) => setValidationRules({ ...validationRules, options: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="例: visa, mastercard, amex"
            />
          </div>
        )}
      </div>
    );
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center p-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h3 className="text-xl font-bold text-gray-900">フィールドスキーマ管理</h3>
        {!showAddForm && (
          <button
            onClick={() => setShowAddForm(true)}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
          >
            新規フィールド追加
          </button>
        )}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md">
          {error}
        </div>
      )}

      {/* Field Suggestions */}
      {suggestions.length > 0 && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h4 className="text-sm font-semibold text-blue-900 mb-3">フィールド候補</h4>
          <div className="space-y-2">
            {suggestions.map((suggestion, index) => (
              <div key={index} className="flex items-center justify-between bg-white p-3 rounded border border-blue-100">
                <div className="flex-1">
                  <div className="text-sm font-medium text-gray-900">{suggestion.field_name}</div>
                  <div className="text-xs text-gray-600">
                    型: {suggestion.field_type} | サンプル値: {JSON.stringify(suggestion.sample_value)} | 信頼度: {(suggestion.confidence * 100).toFixed(0)}%
                  </div>
                </div>
                <button
                  onClick={() => handleApproveSuggestion(suggestion)}
                  className="ml-4 px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 transition-colors"
                >
                  承認
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Add/Edit Form */}
      {showAddForm && (
        <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm">
          <h4 className="text-lg font-semibold mb-4">
            {editingId !== null ? 'フィールド編集' : '新規フィールド'}
          </h4>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="field_name" className="block text-sm font-medium text-gray-700 mb-1">
                フィールド名 <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                id="field_name"
                value={formData.field_name}
                onChange={(e) => setFormData({ ...formData, field_name: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
                maxLength={255}
              />
            </div>

            <div>
              <label htmlFor="field_type" className="block text-sm font-medium text-gray-700 mb-1">
                フィールド型 <span className="text-red-500">*</span>
              </label>
              <select
                id="field_type"
                value={formData.field_type}
                onChange={(e) => setFormData({ ...formData, field_type: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              >
                {FIELD_TYPES.map((type) => (
                  <option key={type.value} value={type.value}>
                    {type.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex items-center">
              <input
                type="checkbox"
                id="is_required"
                checked={formData.is_required}
                onChange={(e) => setFormData({ ...formData, is_required: e.target.checked })}
                className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
              />
              <label htmlFor="is_required" className="ml-2 block text-sm text-gray-700">
                必須フィールド
              </label>
            </div>

            <div>
              <label htmlFor="display_order" className="block text-sm font-medium text-gray-700 mb-1">
                表示順序
              </label>
              <input
                type="number"
                id="display_order"
                value={formData.display_order}
                onChange={(e) => setFormData({ ...formData, display_order: parseInt(e.target.value) || 0 })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                min="0"
              />
            </div>

            {renderValidationRulesForm()}

            <div className="flex space-x-3 pt-2">
              <button
                type="submit"
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
              >
                {editingId !== null ? '更新' : '作成'}
              </button>
              <button
                type="button"
                onClick={resetForm}
                className="px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 transition-colors"
              >
                キャンセル
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Schemas List */}
      <div className="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
        {schemas.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            フィールドスキーマがありません
          </div>
        ) : (
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  順序
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  フィールド名
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  型
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  必須
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  バリデーション
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  操作
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {schemas.map((schema) => (
                <tr key={schema.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm text-gray-900">{schema.display_order}</div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm font-medium text-gray-900">{schema.field_name}</div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm text-gray-600">
                      {FIELD_TYPES.find(t => t.value === schema.field_type)?.label || schema.field_type}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    {schema.is_required ? (
                      <span className="px-2 py-1 text-xs font-semibold rounded-full bg-red-100 text-red-800">
                        必須
                      </span>
                    ) : (
                      <span className="px-2 py-1 text-xs font-semibold rounded-full bg-gray-100 text-gray-800">
                        任意
                      </span>
                    )}
                  </td>
                  <td className="px-6 py-4">
                    <div className="text-sm text-gray-600">
                      {schema.validation_rules ? (
                        <pre className="text-xs">{JSON.stringify(schema.validation_rules, null, 2)}</pre>
                      ) : (
                        '-'
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                    <button
                      onClick={() => handleEdit(schema)}
                      className="text-blue-600 hover:text-blue-900 mr-4"
                    >
                      編集
                    </button>
                    <button
                      onClick={() => setDeleteConfirm(schema.id)}
                      className="text-red-600 hover:text-red-900"
                    >
                      削除
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Delete Confirmation Dialog */}
      {deleteConfirm !== null && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold mb-4">フィールドスキーマの削除</h3>
            <p className="text-gray-700 mb-6">
              このフィールドスキーマを削除してもよろしいですか？
            </p>
            <div className="flex space-x-3 justify-end">
              <button
                onClick={() => setDeleteConfirm(null)}
                className="px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 transition-colors"
              >
                キャンセル
              </button>
              <button
                onClick={() => handleDelete(deleteConfirm)}
                className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors"
              >
                削除
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default FieldSchemaManager;
