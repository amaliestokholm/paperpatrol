class Institute:
    def _get_institute_dir(self, idstr: str):
        institutedir = './workplaces/'
        if idstr.lower() in ['mpia', 'heidelberg']:
            institutedir += 'mpia/'
        elif idstr.lower() in ['sac', 'aarhus']:
            institutedir += 'sac/'
        elif idstr.lower() in ['unibo', 'bologna']:
            institutedir += 'unibo/'
        elif idstr.lower() in ['bham', 'birmingham']:
            institutedir += "bham/"
        return institutedir

    def _get_institute_words(self, idstr: str):
        if idstr.lower() in ['mpia', 'heidelberg']:
            institute_words = ['Heidelberg', 'Max', 'Planck', '69117']
        elif idstr.lower() in ['sac', 'aarhus']:
            institute_words = ['Stellar', 'Astrophysics', 'Centre', 'Aarhus']
        elif idstr.lower() in ['unibo', 'bologna']:
            institute_words = ['Bologna', '40129', 'Italy']
        elif idstr.lower() in ['bham', 'birmingham']:
            institute_words = ["Birmingham", "Edgbaston"]
        return institute_words


    def __init__(self, idstr: str):
        self.institutedir = self._get_institute_dir(idstr)
        self.institute_words = self._get_institute_words(idstr)

