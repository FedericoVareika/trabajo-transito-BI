import dataclasses
import datetime
from input_types import ResultadoSiniestroEnum

@dataclasses.dataclass
class dim_fecha:
    id: int
    fecha: datetime.date
    anio: int
    mes: int
    dia: int

@dataclasses.dataclass
class dim_ubicacion:
    id: int 
    latitud: float
    longitud: float
    descripcion: str
    tipo: str

@dataclasses.dataclass
class dim_calle:
    id: int 
    ubicacion: int 
    nombre: str

@dataclasses.dataclass
class dim_detector:
    id: int 
    codigo: int 
    avenida: str
    int_anterior: str
    int_siguiente: str
    latitud: float
    longitud: float

@dataclasses.dataclass
class fact_medicion:
    fecha_id: int
    detector_id: int 
    hora: datetime.time 
    id_carril: int
    velocidad: float
    volumen: int
    volumen_hora: int

@dataclasses.dataclass
class fact_siniestros:
    fecha_id: int
    ubicacion_id: int 
    tipo_resultado: ResultadoSiniestroEnum
    tipo_siniestro: str
    usa_cinturon: bool | None
    usa_casco: bool | None
    edad: int
    sexo: str | None
