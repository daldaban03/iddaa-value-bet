from data_fetcher import HistoricalDataFetcher
from predictor import Predictor

def test_model():
    print("Test Senaryoları Başlıyor...\n")
    fetcher = HistoricalDataFetcher()
    predictor = Predictor(fetcher)

    matchups = [
        ("Galatasaray", "Fenerbahce"),
        ("Real Madrid", "Barcelona"),
        ("Man City", "Arsenal"),
        ("Bayern Munich", "Dortmund")
    ]

    for home, away in matchups:
        print(f"\n--- {home} vs {away} ---")
        try:
            res = predictor.calculate_probabilities(home, away)
            if res:
                print(f"[{home} Kazanır]: %{res['1']*100:.1f} | [Beraberlik]: %{res['X']*100:.1f} | [{away} Kazanır]: %{res['2']*100:.1f}")
                print(f"Beklenen Gol (xG): {res['Home_xG']} - {res['Away_xG']}")
                print(f"Elo: {res['Home_Elo']} - {res['Away_Elo']}")
                print(f"Sakatlık Etkisi: Ev %{res['Home_Penalty_Pct']} | Dep %{res['Away_Penalty_Pct']}")
                
                # Check metrics validity
                assert 0.8 <= (res['1'] + res['X'] + res['2']) <= 1.05, "Probabilities don't sum to ~1.0"
                assert 0.0 <= res['Poisson_Home'] <= 1.0, "Invalid Poisson probability"
                assert 0.0 <= res['Home_xG'] <= 5.0, "Invalid xG"
            else:
                print("Veri yetersizliği nedeniyle oran hesaplanamadı.")
        except Exception as e:
            print(f"HATA: {e}")

if __name__ == "__main__":
    test_model()
