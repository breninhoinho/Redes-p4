class CamadaEnlace:
    ignore_checksum = False

    def __init__(self, linhas_seriais):
        """
        Inicia uma camada de enlace com um ou mais enlaces, cada um conectado
        a uma linha serial distinta. O argumento linhas_seriais é um dicionário
        no formato {ip_outra_ponta: linha_serial}. O ip_outra_ponta é o IP do
        host ou roteador que se encontra na outra ponta do enlace, escrito como
        uma string no formato 'x.y.z.w'. A linha_serial é um objeto da classe
        PTY (vide camadafisica.py) ou de outra classe que implemente os métodos
        registrar_recebedor e enviar.
        """
        self.enlaces = {}
        self.callback = None
        # Constrói um Enlace para cada linha serial
        for ip_outra_ponta, linha_serial in linhas_seriais.items():
            enlace = Enlace(linha_serial)
            self.enlaces[ip_outra_ponta] = enlace
            enlace.registrar_recebedor(self._callback)

    def registrar_recebedor(self, callback):
        """
        Registra uma função para ser chamada quando dados vierem da camada de enlace
        """
        self.callback = callback

    def enviar(self, datagrama, next_hop):
        """
        Envia datagrama para next_hop, onde next_hop é um endereço IPv4
        fornecido como string (no formato x.y.z.w). A camada de enlace se
        responsabilizará por encontrar em qual enlace se encontra o next_hop.
        """
        # Encontra o Enlace capaz de alcançar next_hop e envia por ele
        self.enlaces[next_hop].enviar(datagrama)

    def _callback(self, datagrama):
        if self.callback:
            self.callback(datagrama)


class Enlace:
    def __init__(self, linha_serial):
        self.linha_serial = linha_serial
        self.linha_serial.registrar_recebedor(self.__raw_recv)
        self.callback = None
        self.buffer = bytearray()
        self.escaping = False  # flag para indicar byte de escape

    def registrar_recebedor(self, callback):
        self.callback = callback

    def enviar(self, datagrama):
        SLIP_END = 0xC0
        SLIP_ESC = 0xDB
        SLIP_ESC_END = 0xDC
        SLIP_ESC_ESC = 0xDD

        quadro = bytearray()
        quadro.append(SLIP_END)  # início do quadro

        for byte in datagrama:
            if byte == SLIP_END:
                quadro += bytes([SLIP_ESC, SLIP_ESC_END])
            elif byte == SLIP_ESC:
                quadro += bytes([SLIP_ESC, SLIP_ESC_ESC])
            else:
                quadro.append(byte)

        quadro.append(SLIP_END)  # fim do quadro

        self.linha_serial.enviar(quadro)

    def __raw_recv(self, dados):
        SLIP_END = 0xC0
        SLIP_ESC = 0xDB
        SLIP_ESC_END = 0xDC
        SLIP_ESC_ESC = 0xDD

        try:
            for byte in dados:
                if byte == SLIP_END:
                    if len(self.buffer) > 0:
                        # quadro completo
                        datagrama = bytes(self.buffer)
                        self.buffer.clear()

                        # descarta datagramas vazios
                        if datagrama and self.callback:
                            self.callback(datagrama)
                    else:
                        # ignora datagramas vazios entre dois ENDs
                        self.buffer.clear()
                        self.escaping = False
                elif self.escaping:
                    if byte == SLIP_ESC_END:
                        self.buffer.append(SLIP_END)
                    elif byte == SLIP_ESC_ESC:
                        self.buffer.append(SLIP_ESC)
                    else:
                        # byte inválido após escape, descarta quadro
                        self.buffer.clear()
                    self.escaping = False
                elif byte == SLIP_ESC:
                    self.escaping = True
                else:
                    self.buffer.append(byte)
        except Exception as e:
            # erro de parsing ou no callback — descarta quadro malformado
            self.buffer.clear()
            self.escaping = False
