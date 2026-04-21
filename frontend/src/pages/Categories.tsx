import React, { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import CategoryManager from '../components/category/CategoryManager';
import FieldSchemaManager from '../components/category/FieldSchemaManager';
import { HelpButton } from '../components/ui/HelpButton/HelpButton';
import type { Category } from '../services/api';
import './Categories.css';

const Categories: React.FC = () => {
  const { user } = useAuth();
  const [selectedCategory, setSelectedCategory] = useState<Category | null>(null);

  return (
    <div className="categories">
      <div className="page-header">
        <h1>カテゴリ管理 <HelpButton title="カテゴリ管理の使い方">
          <div className="help-content">
            <h3>ユーザーストーリー</h3>
            <p>商品・サービスカテゴリを管理し、監視サイトや契約条件の分類基準を整備したい</p>

            <h3>できること</h3>
            <ul>
              <li>カテゴリの追加・編集・削除（名前・説明・カラー設定）</li>
              <li>カテゴリを選択すると、そのカテゴリ専用の動的フィールドスキーマを管理できる</li>
              <li>フィールドスキーマでは、契約条件登録時に表示される追加入力項目を定義できる</li>
            </ul>

            <h3>フィールドスキーマとは</h3>
            <p>カテゴリごとに「定期購入期間」「解約手数料」など業種固有の契約条件項目を自由に追加できる仕組みです。フィールドの型（テキスト・数値・通貨・日付など）やバリデーションルールも設定できます。</p>

            <div className="help-tip">カテゴリ管理・フィールドスキーマ管理は admin ロールのみ操作できます。</div>
          </div>
        </HelpButton></h1>
      </div>

      <CategoryManager
        onCategoryChange={() => setSelectedCategory(null)}
        onCategorySelect={setSelectedCategory}
        selectedCategoryId={selectedCategory?.id ?? null}
      />

      {selectedCategory && user?.role === 'admin' && (
        <div className="categories-schema-section">
          <div className="categories-schema-header">
            <h2>フィールドスキーマ管理 — {selectedCategory.name}</h2>
            <p className="categories-schema-description">
              このカテゴリの動的フィールドを管理します
            </p>
          </div>
          <FieldSchemaManager categoryId={selectedCategory.id} />
        </div>
      )}
    </div>
  );
};

export default Categories;
