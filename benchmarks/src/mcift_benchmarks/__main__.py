import sys

from mcift_benchmarks.cli import main as general_main
from mcift_benchmarks.ims import main as ims_main


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "ims":
        return ims_main(sys.argv[2:])
    return general_main()


if __name__ == "__main__":
    raise SystemExit(main())
