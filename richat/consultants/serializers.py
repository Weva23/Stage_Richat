# serializers.py - Version corrigée avec gestion des erreurs pour la GED

from rest_framework import serializers
from .models import (
    Consultant, Competence, AppelOffre, CriteresEvaluation, MatchingResult,
    DocumentGED, DocumentCategory, DocumentVersion, DocumentAccess,User
)
import logging

logger = logging.getLogger(__name__)


class ConsultantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Consultant
        fields = '__all__'
        extra_kwargs = {
            'user': {'required': False},
            'photo': {'required': False},
            'cv': {'required': False},
            'ville': {'required': False},
            'specialite': {'required': False},
        }

    def validate_email(self, value):
        # Vérifier l'unicité de l'email en excluant l'instance actuelle
        if self.instance:
            if Consultant.objects.exclude(pk=self.instance.pk).filter(email=value).exists():
                raise serializers.ValidationError("Un consultant avec cet email existe déjà.")
        else:
            if Consultant.objects.filter(email=value).exists():
                raise serializers.ValidationError("Un consultant avec cet email existe déjà.")
        return value

    def validate(self, data):
        # Validation des dates de disponibilité
        if 'date_debut_dispo' in data and 'date_fin_dispo' in data:
            if data['date_debut_dispo'] and data['date_fin_dispo']:
                if data['date_debut_dispo'] >= data['date_fin_dispo']:
                    raise serializers.ValidationError({
                        'date_fin_dispo': 'La date de fin doit être postérieure à la date de début.'
                    })
        return data

    def update(self, instance, validated_data):
        # Gestion spéciale des fichiers
        if 'photo' in validated_data and validated_data['photo']:
            # Supprimer l'ancienne photo si elle existe
            if instance.photo and instance.photo.name:
                try:
                    if os.path.exists(instance.photo.path):
                        os.remove(instance.photo.path)
                except Exception as e:
                    logger.warning(f"Erreur lors de la suppression de l'ancienne photo: {e}")
        
        if 'cv' in validated_data and validated_data['cv']:
            # Supprimer l'ancien CV si il existe
            if instance.cv and instance.cv.name:
                try:
                    if os.path.exists(instance.cv.path):
                        os.remove(instance.cv.path)
                except Exception as e:
                    logger.warning(f"Erreur lors de la suppression de l'ancien CV: {e}")

        # Mettre à jour tous les champs
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        return instance


class AppelOffreSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppelOffre
        fields = '__all__'

    def validate_budget(self, value):
        if value <= 0:
            raise serializers.ValidationError("Le budget doit être supérieur à 0.")
        return value

    def validate(self, data):
        # Validation des dates
        if 'date_debut' in data and 'date_fin' in data:
            if data['date_debut'] and data['date_fin']:
                if data['date_debut'] >= data['date_fin']:
                    raise serializers.ValidationError({
                        'date_fin': 'La date de fin doit être postérieure à la date de début.'
                    })
        return data

    def update(self, instance, validated_data):
        # Mettre à jour tous les champs
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        return instance


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role', 'nom', 'created_at']
        extra_kwargs = {
            'password': {'write_only': True}
        }


class CompetenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Competence
        fields = '__all__'


class CriteresEvaluationSerializer(serializers.ModelSerializer):
    class Meta:
        model = CriteresEvaluation
        fields = '__all__'

    def validate_poids(self, value):
        if value <= 0:
            raise serializers.ValidationError("Le poids doit être supérieur à 0.")
        return value


class MatchingResultSerializer(serializers.ModelSerializer):
    consultant_name = serializers.SerializerMethodField()
    appel_offre_name = serializers.SerializerMethodField()

    class Meta:
        model = MatchingResult
        fields = '__all__'

    def get_consultant_name(self, obj):
        return f"{obj.consultant.prenom} {obj.consultant.nom}"

    def get_appel_offre_name(self, obj):
        return obj.appel_offre.nom_projet

class DocumentCategorySerializer(serializers.ModelSerializer):
    document_count = serializers.SerializerMethodField()

    class Meta:
        model = DocumentCategory
        fields = ['id', 'name', 'description', 'document_count']

    def get_document_count(self, obj):
        return obj.documents.count()


class DocumentGEDSerializer(serializers.ModelSerializer):
    file_size_display = serializers.SerializerMethodField()
    folder_type_label = serializers.SerializerMethodField()
    document_type_label = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    appel_offre_nom = serializers.SerializerMethodField()
    consultant_nom = serializers.SerializerMethodField()
    file_extension = serializers.SerializerMethodField()
    file_exists = serializers.SerializerMethodField()

    class Meta:
        model = DocumentGED
        fields = [
            'id', 'title', 'description', 'file', 'file_type', 'document_type',
            'folder_type', 'category', 'consultant', 'appel_offre', 'mission',
            'projet', 'version', 'tags', 'created_by', 'upload_date',
            'modified_date', 'is_public', 'file_size_display', 'folder_type_label',
            'document_type_label', 'created_by_name', 'appel_offre_nom',
            'consultant_nom', 'file_extension', 'file_exists'
        ]

    def get_file_size_display(self, obj):
        """Méthode sécurisée pour obtenir la taille du fichier"""
        try:
            return obj.file_size() if hasattr(obj, 'file_size') else "Inconnu"
        except Exception as e:
            logger.warning(f"Erreur lors du calcul de la taille du fichier pour le document {obj.id}: {str(e)}")
            return "Fichier manquant"

    def get_folder_type_label(self, obj):
        """Obtenir le libellé du type de dossier"""
        folder_choices = dict(DocumentGED.FOLDER_TYPES)
        return folder_choices.get(obj.folder_type, obj.folder_type)

    def get_document_type_label(self, obj):
        """Obtenir le libellé du type de document"""
        doc_choices = dict(DocumentGED.DOCUMENT_TYPES)
        return doc_choices.get(obj.document_type, obj.document_type)

    def get_created_by_name(self, obj):
        """Obtenir le nom de l'utilisateur qui a créé le document"""
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return "Système"

    def get_appel_offre_nom(self, obj):
        """Obtenir le nom de l'appel d'offre associé"""
        if obj.appel_offre:
            return obj.appel_offre.nom_projet
        return None

    def get_consultant_nom(self, obj):
        """Obtenir le nom du consultant associé"""
        if obj.consultant:
            return f"{obj.consultant.prenom} {obj.consultant.nom}"
        return None

    def get_file_extension(self, obj):
        """Obtenir l'extension du fichier"""
        try:
            return obj.get_file_extension()
        except Exception:
            return ""

    def get_file_exists(self, obj):
        """Vérifier si le fichier existe physiquement"""
        try:
            return obj.check_file_exists()
        except Exception as e:
            logger.warning(f"Erreur lors de la vérification de l'existence du fichier pour le document {obj.id}: {str(e)}")
            return False


class DocumentVersionSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = DocumentVersion
        fields = ['id', 'version_number', 'file', 'comments', 'created_by', 'created_at', 'created_by_name']

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return "Système"


class DocumentAccessSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    document_title = serializers.SerializerMethodField()

    class Meta:
        model = DocumentAccess
        fields = ['id', 'document', 'user', 'access_time', 'action', 'user_name', 'document_title']

    def get_user_name(self, obj):
        return obj.user.get_full_name() or obj.user.username

    def get_document_title(self, obj):
        return obj.document.title