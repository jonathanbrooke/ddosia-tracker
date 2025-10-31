import unittest
from src.downloader import Downloader

class TestDownloader(unittest.TestCase):

    def setUp(self):
        self.downloader = Downloader()

    def test_check_for_json(self):
        # Test that the downloader correctly identifies JSON files
        url = "https://www.witha.name/data/"
        json_files = self.downloader.check_for_json(url)
        self.assertIsInstance(json_files, list)
        self.assertTrue(all(file.endswith('.json') for file in json_files))

    def test_download_file(self):
        # Test that the downloader can download a JSON file
        test_url = "https://www.witha.name/data/sample.json"
        result = self.downloader.download_file(test_url)
        self.assertTrue(result)
        # Check if the file exists in the downloads directory
        self.assertTrue(os.path.exists("data/downloads/sample.json"))

if __name__ == '__main__':
    unittest.main()