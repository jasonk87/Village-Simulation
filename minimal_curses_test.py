import curses

def main(stdscr):
    stdscr.clear()
    stdscr.addstr(0, 0, "Minimal curses test. Press any key to exit.")
    stdscr.refresh()
    stdscr.getch()

if __name__ == '__main__':
    try:
        curses.wrapper(main)
        print("Curses test completed successfully.")
    except Exception as e:
        print(f"Curses test failed: {e}")
