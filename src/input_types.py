import dataclasses
import enum
import datetime

@dataclasses.dataclass
class VelocidadPromedio:
    cod_detector: int
    id_carril: int
    fecha: datetime.date
    hora: datetime.time
    dsc_avenida: str
    dsc_int_anterior: str
    dsc_int_siguiente: str
    latitud: float
    longitud: float
    velocidad: float

@dataclasses.dataclass
class ConteoVehicular:
    cod_detector: int
    id_carril: int 
    fecha: datetime.date
    hora: datetime.time
    dsc_avenida: str
    dsc_int_anterior: str
    dsc_int_siguiente: str
    latitud: float
    longitud: float 
    volume: int
    volumen_hora: float

class RolEnum(str, enum.Enum):
    PASAJERO = "PASAJERO"
    CONDUCTOR = "CONDUCTOR"
    PEATON = "PEATON"

class ZonaEnum(str, enum.Enum):
    URBANA = "URBANA"
    SUBURBANA = "SUBURBANA"
    RURAL = "RURAL"

class ResultadoSiniestroEnum(str, enum.Enum):
    HERIDO_LEVE = "HERIDO LEVE"
    HERIDO_GRAVE = "HERIDO GRAVE"
    FALLECIDO_CENTRO_ASISTENCIA = "FALLECIDO EN CENTRO DE ASISTENCIA"
    FALLECIDO_LUGAR = "FALLECIDO EN EN LUGAR"

class VehiculoEnum(str, enum.Enum):
    AUTO = "AUTO"
    MOTO = "MOTO"
    CAMION = "CAMION"
    BICICLETA ="BICICLETA"
    OMNIBUS ="OMNIBUS"
    OTRO ="OTRO"

@dataclasses.dataclass
class Siniestros:
    fecha: datetime.date
    edad: int | None
    rol: RolEnum
    calle: str
    zona: ZonaEnum | None
    tipo_resultado: ResultadoSiniestroEnum
    tipo_siniestro: str
    usa_cinturon: bool | None
    usa_casco: bool | None
    dia_semana: str
    sexo: str | None
    hora: int
    departamento: str
    localidad: str | None
    novedad: int
    tipo_vehiculo: VehiculoEnum | None
    fixed: str | None
    x: int
    y: int
