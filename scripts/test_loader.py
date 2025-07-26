from thothmind.data.smart_loader import (
    load_ticker_data,
    get_available_tickers,
    describe_ticker,
    check_missing_values
)

def main():
    print("🧠 Загрузка списка тикеров...")
    tickers = get_available_tickers()
    print(f"Найдено {len(tickers)} тикеров.")
    print("Первые 5:", tickers[:5])

    ticker = "AAPL"
    print(f"\n📈 Загрузка данных по {ticker}...")
    df = load_ticker_data(ticker)
    print(df.head())

    print("\n📊 Статистика:")
    print(describe_ticker(df))

    print("\n🩺 Пропущенные значения:")
    print(check_missing_values(df))

if __name__ == "__main__":
    main()
