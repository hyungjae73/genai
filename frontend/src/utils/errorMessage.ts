/**
 * FastAPI エラーレスポンスから日本語のエラーメッセージを抽出する。
 *
 * FastAPI は以下の形式でエラーを返す:
 * - 422: { detail: [{ loc: [...], msg: "String should have at least 3 characters", type: "..." }] }
 * - 409/400/404: { detail: "このユーザ名は既に使用されています" }
 * - 500: { detail: "Internal Server Error" }
 *
 * Pydantic の英語バリデーションメッセージを日本語に変換する。
 */

const PYDANTIC_MSG_MAP: Record<string, string> = {
  // String validation
  'String should have at least 3 characters': 'ユーザ名は3文字以上で入力してください',
  'String should have at most 150 characters': 'ユーザ名は150文字以内で入力してください',
  'String should have at least 8 characters': 'パスワードは8文字以上で入力してください',
  'value is not a valid email address': 'メールアドレスの形式が正しくありません',
  // Field required
  'Field required': '必須項目です',
  // Literal validation
  "Input should be 'admin', 'reviewer' or 'viewer'": "ロールは admin / reviewer / viewer のいずれかを選択してください",
};

function translatePydanticMsg(msg: string): string {
  // Exact match
  if (PYDANTIC_MSG_MAP[msg]) return PYDANTIC_MSG_MAP[msg];

  // Partial match patterns
  if (msg.startsWith('String should have at least')) {
    const match = msg.match(/at least (\d+) characters?/);
    if (match) return `${match[1]}文字以上で入力してください`;
  }
  if (msg.startsWith('String should have at most')) {
    const match = msg.match(/at most (\d+) characters?/);
    if (match) return `${match[1]}文字以内で入力してください`;
  }
  if (msg.includes('valid email')) return 'メールアドレスの形式が正しくありません';
  if (msg.includes('Field required')) return '必須項目です';

  // Return original if no translation found (already Japanese or unknown)
  return msg;
}

function fieldNameToJapanese(loc: string[]): string {
  const field = loc[loc.length - 1];
  const map: Record<string, string> = {
    username: 'ユーザ名',
    email: 'メールアドレス',
    password: 'パスワード',
    new_password: '新しいパスワード',
    current_password: '現在のパスワード',
    role: 'ロール',
    name: '名前',
    url: 'URL',
    company_name: '会社名',
  };
  return map[field] || field;
}

/**
 * FastAPI エラーレスポンスから日本語メッセージを抽出する。
 *
 * @param err - catch ブロックで受け取った error オブジェクト
 * @param fallback - デフォルトのエラーメッセージ
 * @returns 日本語のエラーメッセージ文字列
 */
export function extractErrorMessage(err: any, fallback = 'エラーが発生しました'): string {
  const detail = err?.response?.data?.detail;

  if (!detail) return fallback;

  // String detail (409, 400, 404 etc.) — already Japanese from our API
  if (typeof detail === 'string') return detail;

  // Array of validation errors (422)
  if (Array.isArray(detail)) {
    return detail
      .map((d: any) => {
        if (typeof d === 'string') return d;
        const msg = translatePydanticMsg(d.msg || '');
        const loc = d.loc as string[] | undefined;
        if (loc && loc.length > 1) {
          const fieldName = fieldNameToJapanese(loc);
          return `${fieldName}: ${msg}`;
        }
        return msg;
      })
      .join('\n');
  }

  return fallback;
}
