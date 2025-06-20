import logging
import logging.config
import os

def setup_logging():
    logging.config.dictConfig({
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            },
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'standard',
                'level': 'INFO',
                'stream': 'ext://sys.stdout'
            },
            'file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'formatter': 'standard',
                'filename': os.path.join('logs', 'pipeline.log'),
                'maxBytes': 10485760,  # 10MB
                'backupCount': 5,
                'level': 'DEBUG'
            }
        },
        'loggers': {
            '': {
                'handlers': ['console', 'file'],
                'level': 'INFO',
                'propagate': True
            }
        }
    })
    
    # Tạo thư mục logs nếu chưa tồn tại
    os.makedirs('logs', exist_ok=True)