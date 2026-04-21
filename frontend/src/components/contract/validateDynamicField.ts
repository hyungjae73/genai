import type { FieldSchema } from '../../services/api';

/**
 * Validates a dynamic field value against its FieldSchema rules.
 * Returns an error message string, or null if valid.
 *
 * Validates: Requirements 2.1, 2.2, 2.3
 */
export function validateDynamicField(schema: FieldSchema, value: unknown): string | null {
  // is_required check
  if (schema.is_required && (value === null || value === undefined || value === '')) {
    return '必須項目です';
  }

  const rules = schema.validation_rules;
  if (!rules) return null;

  // min check
  if (rules.min !== undefined && Number(value) < rules.min) {
    return `${rules.min} 以上の値を入力してください`;
  }

  // max check
  if (rules.max !== undefined && Number(value) > rules.max) {
    return `${rules.max} 以下の値を入力してください`;
  }

  // pattern check
  if (rules.pattern && !new RegExp(rules.pattern).test(String(value))) {
    return '入力形式が正しくありません';
  }

  // options check
  if (rules.options && !rules.options.includes(value)) {
    return `選択肢から選んでください: ${(rules.options as unknown[]).join(', ')}`;
  }

  return null;
}
