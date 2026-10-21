import random
import unicodedata
from decimal import Decimal

from app.utils.documentos import completar_cnpj, completar_cpf, ean13_digito

PRENOMES = (
    "Ana Beatriz Bruno Camila Carlos Daniela Diego Eduarda Felipe Fernanda Gabriel Giovana Gustavo Helena Igor "
    "Isabela João Júlia Larissa Leonardo Letícia Lucas Luana Marcelo Mariana Mateus Melissa Murilo Natália Nicolas "
    "Otávio Patrícia Paulo Rafaela Renato Sabrina Samuel Sofia Tatiane Thiago Valentina Vinícius Yasmin Wesley "
    "Alice Arthur Bianca Caio Clara Davi Elisa Enzo Heitor Lívia Lorena Miguel Pietra Rodrigo Teresa"
).split()

SOBRENOMES = (
    "Almeida Alves Andrade Araújo Barbosa Batista Borges Cardoso Carvalho Castro Correia Costa Cunha Dias Duarte "
    "Farias Fernandes Ferreira Freitas Gomes Lima Lopes Machado Marques Martins Medeiros Melo Mendes Monteiro Moraes "
    "Moreira Nascimento Nogueira Nunes Oliveira Pereira Pinto Ramos Reis Ribeiro Rocha Santos Silva Soares Teixeira Vieira"
).split()

EMPRESA_A = "Aurora Horizonte Atlântica Boreal Cerrado Cristal Delta Estrela Farol Granito Ipê Jacarandá Lótus Mirante Nova Órbita Pampa Quartzo Rubi Safira Serra Tupã Vértice Zênite".split()
EMPRESA_B = ["Comércio", "Distribuidora", "Suprimentos", "Atacado", "Soluções", "Importadora", "Varejo", "Materiais"]
EMPRESA_C = ["Ltda", "S.A.", "ME", "EIRELI", "Ltda"]

LOGRADOUROS = (
    "Rua das Acácias|Rua dos Ipês|Avenida das Palmeiras|Rua do Comércio|Rua Sete de Setembro|Avenida Brasil|"
    "Rua das Flores|Travessa da Paz|Rua São José|Avenida Central|Rua da Aurora|Rua Bela Vista|Alameda dos Pinheiros|"
    "Rua do Sol|Rua Nova|Avenida dos Estados|Rua Primavera|Rua das Hortênsias|Rua Monte Alegre|Rua Boa Esperança"
).split("|")
BAIRROS = (
    "Centro|Jardim América|Vila Nova|Boa Vista|Santa Cecília|Bela Vista|"
    "Jardim das Flores|Parque Industrial|Vila Esperança|Alto da Serra"
).split("|")

CIDADES = [
    ("São Paulo", "SP", "11"),
    ("Campinas", "SP", "19"),
    ("Santos", "SP", "13"),
    ("Ribeirão Preto", "SP", "16"),
    ("Belo Horizonte", "MG", "31"),
    ("Uberlândia", "MG", "34"),
    ("Juiz de Fora", "MG", "32"),
    ("Curitiba", "PR", "41"),
    ("Londrina", "PR", "43"),
    ("Maringá", "PR", "44"),
    ("Porto Alegre", "RS", "51"),
    ("Caxias do Sul", "RS", "54"),
    ("Florianópolis", "SC", "48"),
    ("Joinville", "SC", "47"),
    ("Salvador", "BA", "71"),
    ("Recife", "PE", "81"),
    ("Fortaleza", "CE", "85"),
    ("Goiânia", "GO", "62"),
    ("Brasília", "DF", "61"),
    ("Vitória", "ES", "27"),
    ("Rio de Janeiro", "RJ", "21"),
    ("Campo Grande", "MS", "67"),
]

DEPOSITOS = [
    ("CD-SP", "Centro de Distribuição São Paulo", "São Paulo", "SP"),
    ("CD-MG", "Centro de Distribuição Minas", "Belo Horizonte", "MG"),
    ("CD-PR", "Centro de Distribuição Sul", "Curitiba", "PR"),
]

CATALOGO: dict[str, list[tuple[str, tuple[int, int], str]]] = {
    "Informática": [
        ("Mouse sem fio", (49, 159), "UN"),
        ("Teclado mecânico ABNT2", (189, 499), "UN"),
        ("Monitor LED 24 pol.", (699, 1299), "UN"),
        ("SSD 480 GB", (189, 349), "UN"),
        ("Memória RAM 16 GB", (229, 399), "UN"),
        ("Hub USB-C 7 em 1", (99, 239), "UN"),
        ("Webcam Full HD", (149, 349), "UN"),
        ("Suporte para notebook", (79, 189), "UN"),
    ],
    "Escritório": [
        ("Caderno universitário 200 fls", (19, 39), "UN"),
        ("Caneta esferográfica azul cx 50", (39, 69), "CX"),
        ("Papel sulfite A4 resma", (29, 49), "PC"),
        ("Grampeador de mesa", (25, 79), "UN"),
        ("Organizador de mesa", (35, 89), "UN"),
        ("Etiquetas adesivas cx 1000", (45, 99), "CX"),
    ],
    "Casa e Cozinha": [
        ("Garrafa térmica 1 L", (59, 139), "UN"),
        ("Jogo de panelas 5 peças", (249, 599), "KIT"),
        ("Faqueiro inox 24 peças", (99, 229), "KIT"),
        ("Pote hermético kit 10", (59, 129), "KIT"),
        ("Cafeteira elétrica", (129, 299), "UN"),
        ("Toalha de banho", (39, 89), "UN"),
    ],
    "Ferramentas": [
        ("Furadeira de impacto", (199, 459), "UN"),
        ("Jogo de chaves 40 peças", (89, 219), "KIT"),
        ("Trena 5 m", (19, 49), "UN"),
        ("Nível de bolha 40 cm", (29, 69), "UN"),
        ("Parafusadeira a bateria", (249, 599), "UN"),
        ("Fita isolante rolo", (5, 15), "RL"),
    ],
    "Eletrônicos": [
        ("Fone de ouvido Bluetooth", (99, 399), "UN"),
        ("Caixa de som portátil", (149, 499), "UN"),
        ("Carregador turbo USB-C", (59, 149), "UN"),
        ("Power bank 10000 mAh", (89, 199), "UN"),
        ("Smartwatch esportivo", (299, 899), "UN"),
        ("Cabo HDMI 2 m", (19, 59), "UN"),
    ],
    "Esporte e Lazer": [
        ("Garrafa squeeze 750 ml", (25, 59), "UN"),
        ("Tapete de yoga", (69, 159), "UN"),
        ("Halteres 2 kg par", (59, 129), "PAR"),
        ("Corda de pular", (19, 49), "UN"),
        ("Bola de futebol", (69, 199), "UN"),
        ("Mochila de trilha 30 L", (149, 349), "UN"),
    ],
    "Papelaria Criativa": [
        ("Lápis de cor 36 cores", (29, 89), "CX"),
        ("Kit pincéis artísticos", (39, 99), "KIT"),
        ("Bloco de desenho A3", (25, 59), "UN"),
        ("Marca-texto cx 6", (19, 39), "CX"),
        ("Tinta guache 12 cores", (19, 45), "CX"),
    ],
    "Limpeza": [
        ("Detergente neutro 5 L", (19, 39), "UN"),
        ("Pano de microfibra pc 5", (19, 45), "PC"),
        ("Rodo 60 cm", (25, 59), "UN"),
        ("Luvas nitrílicas cx 100", (39, 79), "CX"),
        ("Desinfetante 2 L", (9, 25), "UN"),
    ],
}

VARIANTES = ["", " Pro", " Plus", " Compacto", " Premium", " Essencial"]
CORES = ["", " preto", " branco", " azul", " cinza"]


def sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


class GeradorFicticio:
    def __init__(self, semente: int = 42):
        self.r = random.Random(semente)
        self._documentos: set[str] = set()
        self._eans: set[str] = set()

    def cpf(self) -> str:
        while True:
            base = "".join(str(self.r.randint(0, 9)) for _ in range(9))
            if len(set(base)) > 1:
                cpf = completar_cpf(base)
                if cpf not in self._documentos:
                    self._documentos.add(cpf)
                    return cpf

    def cnpj(self) -> str:
        while True:
            base = "".join(str(self.r.randint(0, 9)) for _ in range(8)) + "0001"
            cnpj = completar_cnpj(base)
            if cnpj not in self._documentos:
                self._documentos.add(cnpj)
                return cnpj

    def ean13(self) -> str:
        while True:
            base = "2" + "".join(str(self.r.randint(0, 9)) for _ in range(11))
            codigo = base + ean13_digito(base)
            if codigo not in self._eans:
                self._eans.add(codigo)
                return codigo

    def nome_pessoa(self) -> str:
        return f"{self.r.choice(PRENOMES)} {self.r.choice(SOBRENOMES)} {self.r.choice(SOBRENOMES)}"

    def nome_empresa(self) -> tuple[str, str]:
        fantasia = f"{self.r.choice(EMPRESA_A)} {self.r.choice(EMPRESA_B)}"
        return f"{fantasia} {self.r.choice(EMPRESA_C)}", fantasia

    def email(self, nome: str) -> str:
        partes = sem_acento(nome).lower().replace(".", "").split()
        dominio = self.r.choice(["example.com", "example.org", "example.net"])
        return f"{partes[0]}.{partes[-1]}{self.r.randint(1, 999)}@{dominio}"

    def endereco(self) -> dict:
        cidade, uf, ddd = self.r.choice(CIDADES)
        return {
            "cep": f"{self.r.randint(1000000, 99999999):08d}",
            "logradouro": self.r.choice(LOGRADOUROS),
            "numero": str(self.r.randint(10, 4999)),
            "complemento": self.r.choice(["", "", "", "Apto 12", "Sala 3", "Bloco B", "Casa 2", "Loja 1"]) or None,
            "bairro": self.r.choice(BAIRROS),
            "cidade": cidade,
            "uf": uf,
            "telefone": f"{ddd}9{self.r.randint(10000000, 99999999)}",
        }

    def preco(self, faixa: tuple[int, int]) -> Decimal:
        valor = self.r.uniform(*faixa)
        return Decimal(f"{int(valor)}.{self.r.choice(['90', '99', '00', '50', '49'])}")
