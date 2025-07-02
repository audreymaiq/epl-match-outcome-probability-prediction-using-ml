-- Xóa schema cũ nếu tồn tại để làm lại từ đầu (Cẩn thận khi chạy trên DB đã có dữ liệu)
DROP TABLE IF EXISTS "Odds1x2", "OddsOverUnder", "OddsAsianHandicap", "Matches", "Teams", "Referees", "Seasons", "Leagues" CASCADE;
DROP TYPE IF EXISTS "MatchOutcome";

-- 1. CREATE TYPE ENUM
CREATE TYPE "MatchOutcome" AS ENUM ('H', 'D', 'A');

-- 2. Bảng Leagues
CREATE TABLE "Leagues" (
    "id" SERIAL PRIMARY KEY,
    "code" VARCHAR(10) UNIQUE NOT NULL, -- 'E0' từ cột Div
    "name" VARCHAR(255) UNIQUE NOT NULL
);
COMMENT ON TABLE "Leagues" IS 'Lưu trữ thông tin các giải đấu, ánh xạ từ cột "Div".';

-- 3. Bảng Seasons
CREATE TABLE "Seasons" (
    "id" SERIAL PRIMARY KEY,
    "league_id" INT NOT NULL REFERENCES "Leagues"("id") ON DELETE CASCADE,
    "name" VARCHAR(50) UNIQUE NOT NULL, -- Ví dụ: '2024-2025'
    "start_year" INT NOT NULL,
    "end_year" INT NOT NULL
);
COMMENT ON TABLE "Seasons" IS 'Lưu trữ thông tin các mùa giải.';

-- 4. Bảng Teams
CREATE TABLE "Teams" (
    "id" SERIAL PRIMARY KEY,
    "name" VARCHAR(255) UNIQUE NOT NULL
);
COMMENT ON TABLE "Teams" IS 'Lưu trữ danh sách các đội bóng.';

-- 5. Bảng Referees
CREATE TABLE "Referees" (
    "id" SERIAL PRIMARY KEY,
    "name" VARCHAR(255) UNIQUE NOT NULL
);
COMMENT ON TABLE "Referees" IS 'Lưu trữ danh sách các trọng tài.';

-- 6. Bảng Matches (Bảng trung tâm)
CREATE TABLE "Matches" (
    "id" SERIAL PRIMARY KEY,
    "season_id" INT NOT NULL REFERENCES "Seasons"("id"),
    "match_datetime" TIMESTAMP NOT NULL,
    "home_team_id" INT NOT NULL REFERENCES "Teams"("id"),
    "away_team_id" INT NOT NULL REFERENCES "Teams"("id"),
    "referee_id" INT REFERENCES "Referees"("id"),

    -- Kết quả trận đấu
    "fthg" INT NOT NULL, -- Full Time Home Goals
    "ftag" INT NOT NULL, -- Full Time Away Goals
    "ftr" "MatchOutcome" NOT NULL, -- Full Time Result
    "hthg" INT NOT NULL, -- Half Time Home Goals
    "htag" INT NOT NULL, -- Half Time Away Goals
    "htr" "MatchOutcome" NOT NULL, -- Half Time Result

    -- Thống kê trong trận
    "hs" INT, -- Home Shots
    "as" INT, -- Away Shots
    "hst" INT, -- Home Shots on Target
    "ast" INT, -- Away Shots on Target
    "hf" INT, -- Home Fouls
    "af" INT, -- Away Fouls
    "hc" INT, -- Home Corners
    "ac" INT, -- Away Corners
    "hy" INT, -- Home Yellow Cards
    "ay" INT, -- Away Yellow Cards
    "hr" INT, -- Home Red Cards
    "ar" INT, -- Away Red Cards

    CONSTRAINT uq_match UNIQUE (season_id, home_team_id, away_team_id, match_datetime)
);
COMMENT ON TABLE "Matches" IS 'Bảng chính lưu trữ thông tin và kết quả của mỗi trận đấu.';

-- 7. Bảng Odds1x2 (Tỷ lệ Thắng-Hòa-Thua)
CREATE TABLE "Odds1x2" (
    "id" SERIAL PRIMARY KEY,
    "match_id" INT UNIQUE NOT NULL REFERENCES "Matches"("id") ON DELETE CASCADE,

    -- Tỷ lệ mở kèo
    "b365h" DECIMAL(5,2), "b365d" DECIMAL(5,2), "b365a" DECIMAL(5,2),
    "bwh" DECIMAL(5,2), "bwd" DECIMAL(5,2), "bwa" DECIMAL(5,2),
    "bfh" DECIMAL(5,2), "bfd" DECIMAL(5,2), "bfa" DECIMAL(5,2),
    "psh" DECIMAL(5,2), "psd" DECIMAL(5,2), "psa" DECIMAL(5,2),
    "whh" DECIMAL(5,2), "whd" DECIMAL(5,2), "wha" DECIMAL(5,2),
    "one_xb_h" DECIMAL(5,2), "one_xb_d" DECIMAL(5,2), "one_xb_a" DECIMAL(5,2),
    "max_h" DECIMAL(5,2), "max_d" DECIMAL(5,2), "max_a" DECIMAL(5,2),
    "avg_h" DECIMAL(5,2), "avg_d" DECIMAL(5,2), "avg_a" DECIMAL(5,2),
    "bfeh" DECIMAL(5,2), "bfed" DECIMAL(5,2), "bfea" DECIMAL(5,2),

    -- Tỷ lệ đóng kèo
    "b365ch" DECIMAL(5,2), "b365cd" DECIMAL(5,2), "b365ca" DECIMAL(5,2),
    "bwch" DECIMAL(5,2), "bwcd" DECIMAL(5,2), "bwca" DECIMAL(5,2),
    "bfch" DECIMAL(5,2), "bfcd" DECIMAL(5,2), "bfca" DECIMAL(5,2),
    "psch" DECIMAL(5,2), "pscd" DECIMAL(5,2), "psca" DECIMAL(5,2),
    "whch" DECIMAL(5,2), "whcd" DECIMAL(5,2), "whca" DECIMAL(5,2),
    "one_xb_ch" DECIMAL(5,2), "one_xb_cd" DECIMAL(5,2), "one_xb_ca" DECIMAL(5,2),
    "max_ch" DECIMAL(5,2), "max_cd" DECIMAL(5,2), "max_ca" DECIMAL(5,2),
    "avg_ch" DECIMAL(5,2), "avg_cd" DECIMAL(5,2), "avg_ca" DECIMAL(5,2),
    "bfech" DECIMAL(5,2), "bfecd" DECIMAL(5,2), "bfeca" DECIMAL(5,2)
);
COMMENT ON TABLE "Odds1x2" IS 'Lưu trữ tỷ lệ cược 1x2 (Thắng-Hòa-Thua) cho mỗi trận.';

-- 8. Bảng OddsOverUnder (Tỷ lệ Tài/Xỉu 2.5)
CREATE TABLE "OddsOverUnder" (
    "id" SERIAL PRIMARY KEY,
    "match_id" INT UNIQUE NOT NULL REFERENCES "Matches"("id") ON DELETE CASCADE,

    -- Tỷ lệ mở kèo
    "b365_over" DECIMAL(5,2), "b365_under" DECIMAL(5,2),
    "p_over" DECIMAL(5,2), "p_under" DECIMAL(5,2),
    "max_over" DECIMAL(5,2), "max_under" DECIMAL(5,2),
    "avg_over" DECIMAL(5,2), "avg_under" DECIMAL(5,2),
    "bfe_over" DECIMAL(5,2), "bfe_under" DECIMAL(5,2),

    -- Tỷ lệ đóng kèo
    "b365c_over" DECIMAL(5,2), "b365c_under" DECIMAL(5,2),
    "pc_over" DECIMAL(5,2), "pc_under" DECIMAL(5,2),
    "maxc_over" DECIMAL(5,2), "maxc_under" DECIMAL(5,2),
    "avgc_over" DECIMAL(5,2), "avgc_under" DECIMAL(5,2),
    "bfec_over" DECIMAL(5,2), "bfec_under" DECIMAL(5,2)
);
COMMENT ON TABLE "OddsOverUnder" IS 'Lưu trữ tỷ lệ cược Tài/Xỉu 2.5 bàn cho mỗi trận.';


-- 9. Bảng OddsAsianHandicap (Tỷ lệ Chấp Châu Á)
CREATE TABLE "OddsAsianHandicap" (
    "id" SERIAL PRIMARY KEY,
    "match_id" INT UNIQUE NOT NULL REFERENCES "Matches"("id") ON DELETE CASCADE,

    -- Kèo và tỷ lệ mở kèo
    "ahh" DECIMAL(4,2), -- Kèo chấp
    "b365ahh" DECIMAL(5,2), "b365aha" DECIMAL(5,2),
    "pahh" DECIMAL(5,2), "paha" DECIMAL(5,2),
    "maxahh" DECIMAL(5,2), "maxaha" DECIMAL(5,2),
    "avgahh" DECIMAL(5,2), "avgaha" DECIMAL(5,2),
    "bfeahh" DECIMAL(5,2), "bfeaha" DECIMAL(5,2),
    
    -- Kèo và tỷ lệ đóng kèo
    "ahch" DECIMAL(4,2), -- Kèo chấp lúc đóng
    "b365cahh" DECIMAL(5,2), "b365caha" DECIMAL(5,2),
    "pcahh" DECIMAL(5,2), "pcaha" DECIMAL(5,2),
    "maxcahh" DECIMAL(5,2), "maxcaha" DECIMAL(5,2),
    "avgcahh" DECIMAL(5,2), "avgcaha" DECIMAL(5,2),
    "bfecahh" DECIMAL(5,2), "bfecaha" DECIMAL(5,2)
);
COMMENT ON TABLE "OddsAsianHandicap" IS 'Lưu trữ tỷ lệ cược Chấp Châu Á cho mỗi trận.';