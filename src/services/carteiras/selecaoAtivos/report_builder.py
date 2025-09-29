import pandas as pd

def export_deri_mevar(dfs: dict, filename: str, only_group_sheets: bool = False):
    """
    Exporta:
      - se only_group_sheets=True: APENAS as abas de cada setor (sem 'Overview')
      - caso contrário: mantém comportamento padrão (Overview + abas)
    """
    if not dfs:
        print("⚠️ Nenhum DataFrame para exportar")
        return

    print(f"📊 Exportando {len(dfs)} abas para Excel...")

    try:
        with pd.ExcelWriter(filename, engine="openpyxl") as writer:
            if only_group_sheets:
                # escreve só as abas dos grupos com colunas na ordem que vier no DF
                for grupo, df in dfs.items():
                    if df is not None and not df.empty:
                        sheet = str(grupo)[:31]
                        df.to_excel(writer, sheet_name=sheet, index=False)
                        print(f"  📈 {sheet}: {len(df)} linhas na aba '{sheet}'")
                return

            # --------- modo antigo (Overview + abas) ---------
            frames = []
            for grupo, df in dfs.items():
                if df is None or df.empty:
                    continue
                tmp = df.copy()
                tmp.insert(0, "Grupo", grupo)
                frames.append(tmp)
            

            for grupo, df in dfs.items():
                if df is not None and not df.empty:
                    sheet = str(grupo)[:31]
                    df.to_excel(writer, sheet_name=sheet, index=False)
                    print(f"  📈 {sheet}: {len(df)} linhas na aba '{sheet}'")

        print(f"✅ Arquivo Excel criado: {filename}")

    except Exception as e:
        print(f"❌ Erro ao criar arquivo Excel: {e}")
        # fallback CSV único por aba
        for grupo, df in dfs.items():
            if df is not None and not df.empty:
                p = filename.replace(".xlsx", f"_{str(grupo).lower().replace(' ', '_')}.csv")
                df.to_csv(p, index=False, encoding="utf-8")
                print(f"  💾 Fallback CSV salvo: {p}")