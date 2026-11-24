// Premium Worker company-material classification.
export function classifyDisclosureTitle(title) {
  const text = String(title || "");

  // 1. ファンダとして必ず優先したい開示
  if (
    /決算短信|四半期決算|決算説明(?:会)?資料|決算補足説明資料/.test(text) ||
    /業績予想|業績修正|上方修正|下方修正|通期予想|連結予想/.test(text) ||
    /配当|増配|減配|復配|無配|剰余金|自己株式|自社株|株主還元/.test(text) ||
    /資本コスト|株価を意識|PBR|ROE|資本政策|資本効率/.test(text) ||
    /中期経営|中計|経営計画|事業計画/.test(text) ||
    /月次|受注|売上速報|販売状況|稼働率/.test(text) ||
    /買収|譲渡|取得|売却|合併|会社分割|事業譲受|事業譲渡/.test(text) ||
    /提携|資本業務|業務提携|共同開発|大型受注|契約締結/.test(text) ||
    /固定資産|特別利益|特別損失|減損|貸倒|投資有価証券/.test(text) ||
    /新株予約権|第三者割当|公募増資|CB|MSワラント|希薄化/.test(text)
  ) {
    return "fundamental";
  }

  // 2. 人事でも、ファンダ/ガバナンス上重要になりやすいもの
  if (
    /代表取締役|社長交代|CEO|CFO|会長交代/.test(text) ||
    /監査法人|会計監査人|不適切会計|不正|調査委員会|特別調査/.test(text) ||
    /訴訟|行政処分|規制|上場維持|改善報告|監理銘柄|特設注意市場/.test(text)
  ) {
    return "fundamental";
  }

  // 3. 原則スルーでよい通常開示
  if (
    /人事異動|役員人事|執行役員|組織変更|定款一部変更|支配株主等に関する事項/.test(text) ||
    /株主総会|招集通知|独立役員届出|コーポレート・ガバナンス報告書/.test(text)
  ) {
    return "routine";
  }

  return "other";
}
