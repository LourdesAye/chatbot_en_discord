
from bot.manejador_de_bot import DiscordChatbot
from configuracion.repository import RepositorioYAML
from validador import Validador


def main():
    repositorio = RepositorioYAML()
    validador = Validador(repositorio)
    bot = DiscordChatbot(validador)
    bot.run()

if __name__ == "__main__":
    main()