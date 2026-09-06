"""Native Windows application, also used as its isolated speech recognition subprocess."""
import sys
from engine import recognize

if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--recognize':
        if sys.stdout:
            sys.stdout.reconfigure(encoding='utf-8')
        if sys.stderr:
            sys.stderr.reconfigure(encoding='utf-8')
        recognize(sys.argv[2])
    else:
        from ui import main
        main()
