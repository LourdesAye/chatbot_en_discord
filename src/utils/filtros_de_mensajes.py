import re
from abc import ABC, abstractmethod


class EstrategiaFiltro(ABC): 
    
    @abstractmethod 
    def aplicar(self, texto: str) -> bool: 
        pass 

    @abstractmethod 
    def nombre(self) -> str: 
        pass 

class FiltroContenidoVacio(EstrategiaFiltro): 
   
    def aplicar(self, texto: str) -> bool: 
        return texto.strip() == ""
    
    def nombre(self) -> str: 
        return "mensajes_solo_vacios"

class FiltroContenidoIrrelevanteVisual(EstrategiaFiltro): 
    
    def aplicar(self, texto: str) -> bool: 
        texto = texto.strip().lower()
        solo_emojis = re.fullmatch(r"[\s\U0001F300-\U0001FAFF\U00002600-\U000026FF\U00002700-\U000027BF]+", texto)
        es_link_tenor_giphy = re.fullmatch(r"(https?:\/\/)?(www\.)?(tenor|giphy)\.com\S*", texto)
        es_sticker_gif = texto in {"sticker", "gif"}
        return bool(solo_emojis or es_link_tenor_giphy or es_sticker_gif)
   
    def nombre(self) -> str: 
        return "mensajes_solo_emojis_stickers_gifs"

class FiltroSoloNumerosSignos(EstrategiaFiltro):
    def aplicar(self, texto: str) -> bool: 
        return bool(re.fullmatch(r"[+\d\s]+", texto))
    
    def nombre(self) -> str: 
        return "mensajes_solo_numeros_signos"

class FiltroSoloSimbolos(EstrategiaFiltro): 
   
    def aplicar(self, texto: str) -> bool: 
        texto = texto.strip()
        return not re.search(r'[a-zA-Z0-9áéíóúÁÉÍÓÚñÑ]', texto)
   
    def nombre(self) -> str:
        return "mensajes_solo_simbolos"
    

    
