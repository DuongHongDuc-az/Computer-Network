from prompt_toolkit import PromptSession, print_formatted_text , ANSI
from prompt_toolkit.patch_stdout import patch_stdout
from colorama import  Fore, Style,init

init(autoreset=True)

def print_color(text):
    print_formatted_text(ANSI(text))

