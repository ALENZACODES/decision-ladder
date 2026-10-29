"""Legal descriptions where cities publish them: Calgary (short legal), Edmonton (legal description).
Vancouver, Langley Township and Victoria already carry plan/lot/PID fields in their raw files."""
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from fetch_assessments import pull

if __name__ == "__main__":
    pull("https://data.calgary.ca/resource/4bsw-nn7w.json", "roll_number,address,short_legal", "assessment_class='RE'", "calgary_legal")
    pull("https://data.edmonton.ca/resource/dkk9-cj3x.json", "account_number,house_number,street_name,legal_description",
         "account_number IS NOT NULL", "edmonton_legal")
