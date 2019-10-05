import boto3
import json
import shutil
import os
from requests import session


lam = boto3.client('lambda')
s3 = boto3.resource('s3')
s3bucket = "TU_BUCKET_PERSONAL"


def lambda_handler(event, context):
    #una técnica para detectar el ambiente de ejecución: si está seteado AWS_EXECUTION_ENV siginfica que estoy en lambda.
    if os.environ.get('AWS_EXECUTION_ENV') is not None:
        isLambda = 1
    else:
        isLambda = 0
    
    base_path = './archivos/'
    #si estoy en lambda cambio el base_path al /tmp/ (el único lugar con permisos de escritura del contenedor)
    #el límite de /tmp/ son 500 MB ojo!
    if isLambda == 1:
        print("Runtime API:", os.environ['AWS_EXECUTION_ENV'])
        base_path = '/tmp/'
    
    backup_funciones(base_path)

def backup_capas(base_path):
    response = lam.list_layers()
    layers = response['Layers']
    print("Se econtraron", len(layers), "Capas")
    for layer in response['Layers']:
        print("\nProcesando [", layer['LayerName'], ":", layer['LayerArn'], "]\n", 100*"*", "\n")
        print("Version:", layer['LatestMatchingVersion']['Version'])
        print("Runtimes:", repr(layer['LatestMatchingVersion']['CompatibleRuntimes']))
        full_layer = lam.get_layer_version_by_arn(
            Arn=layer['LatestMatchingVersion']['LayerVersionArn']
        )

        config_filename = layer['LayerName']+".json"
        code_filename = layer['LayerName']+".zip"

        config_json = json.dumps(full_layer)
        with open(base_path+config_filename, "w") as config:
            config.write(config_json)
        with session() as d:
            peticion = d.get(full_layer['Content']['Location'], stream=True)
            out_file = open(base_path+code_filename, 'wb')
            out_file.write(peticion.content)
            out_file.close()

        s3.Bucket(s3bucket).upload_file(base_path+config_filename,'layers/' + config_filename)

        print("\nArchivo de Configuracion:", config_filename)
        print("Subido a:", s3bucket+'/' +'layers/' + config_filename, "\n")

        with open(base_path+code_filename, 'rb') as data:
            s3.Bucket(s3bucket).upload_fileobj(data, 'layers/' + code_filename)

        print("Archivo de Codigo Fuente:", code_filename)
        print("Subido a:", s3bucket+'/' + 'layers/' + code_filename, "\n")
        
def backup_funciones(base_path):

    response = lam.list_functions()
    funciones = response['Functions'] #Todas las funciones

    print("Encontramos {} funciones".format(len (funciones)))

    for fn in funciones:
        layers = 0
        if hasattr(fn, 'Layers'):
            layers = len(fn['Layers'])

        print("\nProcesando [{}] : {}\n".format(fn['FunctionName'], fn['FunctionArn']))
        print("Runtime: {}\n Descripcion:{}\n Tamaño: {}\n Capas:{}\n".format(
            fn['Runtime'],
            fn['Description'], 
            fn['CodeSize'], 
            layers))

        full_fn = lam.get_function(
            FunctionName=fn['FunctionName']
        ) #el detalle de la funcion incluyendo el código fuente

        if hasattr(full_fn['Configuration'], 'Tags'):
            full_fn['Configuration']['Tags'] = full_fn['Tags']

        config_json = json.dumps(full_fn['Configuration']) # un json con con la configuración de la función.
        config_filename = fn['FunctionName']+".json"
        code_filename = fn['FunctionName']+".zip"
        with open(base_path+config_filename, "w") as config:
            config.write(config_json) # Si es lambda se guardará en /tmp/ si no en /archivos/ (debe existir la subcarpeta)


        #acá la magia para obtener la descarga desde la URL pre-firmada
        #usamos la librería requests que realiza la http request con sesiones...
        with session() as d:
            peticion = d.get(full_fn['Code']['Location'], stream=True)
            out_file = open(base_path+code_filename, 'wb')
            out_file.write(peticion.content)
            out_file.close()

        print("Codigo Fuente:", code_filename)

        #Utilizamos el Bucket de destino para guardar el código y el archivo de configuración. 
        #Elegí guardarlo en subcarpetas separados por runtime, pero es a elección de cada uno :)
        s3.Bucket(s3bucket).upload_file(base_path+config_filename,
                                        fn['Runtime']+'/' + config_filename)
        with open(base_path+code_filename, 'rb') as data:
            #upload_fileobj permite la subida de archivos binarios (ojo de debe abrirse como 'rb': read and binary)
            s3.Bucket(s3bucket).upload_fileobj(
                data, fn['Runtime']+'/' + code_filename)

        print("\nArchivo de Configuracion:", config_filename)
        print("Subido a:", s3bucket+'/' +
              fn['Runtime']+'/' + config_filename, "\n")
        print("Archivo de Codigo Fuente:", code_filename)
        print("Subido a:", s3bucket+'/' +
              fn['Runtime']+'/' + code_filename, "\n")



#backup_capas()
#backup_funciones(base_path)