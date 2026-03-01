"""Tests for the disk metrics module."""

from unittest.mock import MagicMock, patch

from infraprobe.system.disk import get_disk_usage


class TestGetDiskUsage:
    """Test disk usage collection."""

    @patch("infraprobe.system.disk.os.statvfs")
    def test_calculates_usage(self, mock_statvfs: MagicMock) -> None:
        """Should correctly calculate disk usage from statvfs."""
        mock_stat = MagicMock()
        mock_stat.f_frsize = 4096       # 4KB block size
        mock_stat.f_blocks = 2621440    # ~10GB total
        mock_stat.f_bfree = 1310720     # ~5GB free (root)
        mock_stat.f_bavail = 1048576    # ~4GB free (non-root)
        mock_stat.f_files = 655360
        mock_stat.f_ffree = 600000
        mock_statvfs.return_value = mock_stat

        results = get_disk_usage(paths=["/"])
        assert len(results) == 1
        assert results[0].mountpoint == "/"
        assert results[0].total_gb > 0
        assert results[0].used_percent > 0
        assert results[0].used_percent < 100
