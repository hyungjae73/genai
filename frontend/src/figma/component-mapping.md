# Figma ↔ コード コンポーネントマッピング

## 概要

本ドキュメントは、Figma SDS（Simple Design System）のコンポーネントと、フロントエンドコードのReactコンポーネントの対応関係を管理する。デザインとコードの同期状態を追跡し、継続的なUX改善を支援する。

## コンポーネント対応表

| figmaName | codePath | status |
|-----------|----------|--------|
| Button | components/ui/Button/Button.tsx | synced |
| Badge | components/ui/Badge/Badge.tsx | synced |
| Card | components/ui/Card/Card.tsx | synced |
| Table | components/ui/Table/Table.tsx | synced |
| Modal | components/ui/Modal/Modal.tsx | synced |
| Input | components/ui/Input/Input.tsx | synced |
| Select | components/ui/Select/Select.tsx | synced |
| Sidebar | components/ui/Sidebar/Sidebar.tsx | synced |
| ThemeToggle | components/ui/ThemeToggle/ThemeToggle.tsx | synced |

### ステータス定義

- **synced**: Figmaデザインとコード実装が同期済み
- **outdated**: Figmaデザインが更新され、コード側の反映が必要
- **new**: Figmaで新規定義されたが、コード実装が未着手

## デザイントークン抽出 → CSS変換手順

### 1. Figma Variablesからトークンを抽出

1. Kiro Figma Powerを使用してFigmaファイルにアクセスする
2. Figma VariablesコレクションからPrimitive/Semanticトークンを取得する
3. 取得したトークンをJSON中間形式に変換する

```typescript
// トークン中間表現
interface DesignToken {
  name: string;       // e.g., "blue-600"
  value: string;      // e.g., "#2563eb"
  type: 'color' | 'spacing' | 'fontSize' | 'borderRadius' | 'shadow';
  layer: 'primitive' | 'semantic';
  mode?: 'light' | 'dark';
}
```

### 2. CSS変数ファイルに変換

1. プリミティブトークン → `tokens/primitives.css` の `:root` セレクタに記述
2. ライトモード用セマンティックトークン → `tokens/semantic-light.css` の `:root, [data-theme="light"]` セレクタに記述
3. ダークモード用セマンティックトークン → `tokens/semantic-dark.css` の `[data-theme="dark"]` セレクタに記述
4. セマンティックトークンの値はプリミティブトークンの `var()` 参照とする

### 3. 変換例

Figma Variable: `Blue/600 = #2563eb`

```css
/* primitives.css */
:root {
  --blue-600: #2563eb;
}

/* semantic-light.css */
:root, [data-theme="light"] {
  --color-accent: var(--blue-600);
}
```

## Kiro Figma Powerを活用したコンポーネント仕様取得手順

### 1. Figma Powerの有効化

Kiro IDEでFigma Powerを有効化し、FigmaファイルURLを指定してアクセスする。

### 2. コンポーネント仕様の取得

1. Figma Power の `activate` アクションでFigma Powerを起動する
2. 対象コンポーネントのFigmaノードIDを指定して仕様を取得する
3. 取得した仕様からprops、バリアント、サイズ、スタイル情報を抽出する

### 3. Code Connect定義の生成

取得した仕様に基づき、FigmaコンポーネントとReactコンポーネントの対応を定義する。

```typescript
// 例: figma/Button.figma.tsx
import figma from '@figma/code-connect';
import { Button } from '../components/ui/Button/Button';

figma.connect(Button, 'https://figma.com/design/xxx/Button', {
  props: {
    variant: figma.enum('Variant', {
      Primary: 'primary',
      Secondary: 'secondary',
      Danger: 'danger',
    }),
    size: figma.enum('Size', { Small: 'sm', Medium: 'md', Large: 'lg' }),
    label: figma.string('Label'),
    disabled: figma.boolean('Disabled'),
  },
  example: (props) => <Button {...props}>{props.label}</Button>,
});
```

## デザイン変更時のコード反映手順

Figmaでデザインが変更された場合、以下の4ステップで反映する。

### Step 1: トークン更新

1. Figma Variablesの変更内容を確認する
2. 変更されたプリミティブトークンを `tokens/primitives.css` に反映する
3. 変更されたセマンティックトークンを `tokens/semantic-light.css` / `tokens/semantic-dark.css` に反映する
4. `tokens/index.css` のインポート順序が正しいことを確認する

### Step 2: コンポーネント更新

1. 変更の影響を受けるコンポーネントを本マッピング表で特定する
2. コンポーネントのprops、バリアント、スタイルを更新する
3. コンポーネントのユニットテストを更新・実行する
4. マッピング表のstatusを `synced` に更新する

### Step 3: ページ更新

1. 更新されたコンポーネントを使用しているページを特定する
2. ページ固有のスタイル調整が必要な場合は対応する
3. レスポンシブレイアウトへの影響を確認する

### Step 4: テスト

1. ユニットテストを実行する: `npx vitest run`
2. プロパティベーステストを実行し、トークン整合性・アクセシビリティ等を検証する
3. ライトモード・ダークモード両方で表示を確認する
4. モバイル・タブレット・デスクトップの各ブレークポイントで表示を確認する

### 差異検出時の対応

Figmaデザインとコード実装の間に視覚的な差異が検出された場合:

1. マッピング表の該当エントリのstatusを `outdated` に変更する
2. 差異の内容を記録する（どのプロパティが乖離しているか）
3. 修正タスクを作成し、優先度を設定する
4. 修正完了後、statusを `synced` に戻す
