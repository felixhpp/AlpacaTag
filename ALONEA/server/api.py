from collections import Counter
from itertools import chain

from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, generics, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from .models import Project, Label, Document, SequenceRecommendation
from .permissions import IsAdminUserAndWriteOnly, IsProjectUser, IsOwnAnnotation
from .serializers import ProjectSerializer, LabelSerializer, DocumentSerializer

import re
import time
import os
import sys
sys.path.append("..")

import tensorflow as tf
import active


# from anago.utils import download
# import anago

session = tf.Session()
graph = tf.get_default_graph()
model = active.Sequence()

# url = 'https://s3-ap-northeast-1.amazonaws.com/dev.tech-sketch.jp/chakki/public/conll2003_en.zip'
# weights, params, preprocessor = download(url)
# with graph.as_default():
#     model = anago.Sequence.load(weights, params, preprocessor)

class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    pagination_class = None
    permission_classes = (IsAuthenticated, IsAdminUserAndWriteOnly)

    def get_queryset(self):
        return self.request.user.projects

    @action(methods=['get'], detail=True)
    def progress(self, request, pk=None):
        project = self.get_object()
        return Response(project.get_progress(self.request.user))


class LabelList(generics.ListCreateAPIView):
    queryset = Label.objects.all()
    serializer_class = LabelSerializer
    pagination_class = None
    permission_classes = (IsAuthenticated, IsProjectUser, IsAdminUserAndWriteOnly)

    def get_queryset(self):
        queryset = self.queryset.filter(project=self.kwargs['project_id'])
        return queryset

    def perform_create(self, serializer):
        project = get_object_or_404(Project, pk=self.kwargs['project_id'])
        serializer.save(project=project)


class ProjectStatsAPI(APIView):
    pagination_class = None
    permission_classes = (IsAuthenticated, IsProjectUser, IsAdminUserAndWriteOnly)

    def get(self, request, *args, **kwargs):
        p = get_object_or_404(Project, pk=self.kwargs['project_id'])
        labels = [label.text for label in p.labels.all()]
        users = [user.username for user in p.users.all()]
        docs = [doc for doc in p.documents.all()]
        nested_labels = [[a.label.text for a in doc.get_annotations()] for doc in docs]
        nested_users = [[a.user.username for a in doc.get_annotations()] for doc in docs]

        label_count = Counter(chain(*nested_labels))
        label_data = [label_count[name] for name in labels]

        user_count = Counter(chain(*nested_users))
        user_data = [user_count[name] for name in users]

        response = {'label': {'labels': labels, 'data': label_data},
                    'user': {'users': users, 'data': user_data}}

        return Response(response)


class LabelDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Label.objects.all()
    serializer_class = LabelSerializer
    permission_classes = (IsAuthenticated, IsProjectUser, IsAdminUser)

    def get_queryset(self):
        queryset = self.queryset.filter(project=self.kwargs['project_id'])

        return queryset

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        obj = get_object_or_404(queryset, pk=self.kwargs['label_id'])
        self.check_object_permissions(self.request, obj)

        return obj


class DocumentList(generics.ListCreateAPIView):
    queryset = Document.objects.all()
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    search_fields = ('text', )
    permission_classes = (IsAuthenticated, IsProjectUser, IsAdminUserAndWriteOnly)

    def get_serializer_class(self):
        project = get_object_or_404(Project, pk=self.kwargs['project_id'])
        self.serializer_class = project.get_document_serializer()

        return self.serializer_class

    def get_queryset(self):
        queryset = self.queryset.filter(project=self.kwargs['project_id'])
        if not self.request.query_params.get('is_checked'):
            return queryset

        project = get_object_or_404(Project, pk=self.kwargs['project_id'])
        is_null = self.request.query_params.get('is_checked') == 'true'
        queryset = project.get_documents(is_null).distinct()

        return queryset

class DocumentDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    permission_classes = (IsAuthenticated, IsProjectUser, IsAdminUser)

    def get_queryset(self):
        queryset = self.queryset.filter(project=self.kwargs['project_id'])
        return queryset

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        obj = get_object_or_404(queryset, pk=self.kwargs['doc_id'])
        self.check_object_permissions(self.request, obj)
        return obj

    def patch(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)

class AnnotationList(generics.ListCreateAPIView):
    pagination_class = None
    permission_classes = (IsAuthenticated, IsProjectUser)

    def get_serializer_class(self):
        project = get_object_or_404(Project, pk=self.kwargs['project_id'])
        self.serializer_class = project.get_annotation_serializer()

        return self.serializer_class

    def get_queryset(self):
        project = get_object_or_404(Project, pk=self.kwargs['project_id'])
        document = project.documents.get(id=self.kwargs['doc_id'])
        self.queryset = document.get_annotations()
        self.queryset = self.queryset.filter(user=self.request.user)

        return self.queryset

    def perform_create(self, serializer):
        doc = get_object_or_404(Document, pk=self.kwargs['doc_id'])
        serializer.save(document=doc, user=self.request.user)

    def delete(self, request, *args, **kwargs):
        doc = get_object_or_404(Document, pk=self.kwargs['doc_id'])
        doc.delete_annotations()
        return Response(status=status.HTTP_204_NO_CONTENT)

class AnnotationDetail(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = (IsAuthenticated, IsProjectUser, IsOwnAnnotation)

    def get_serializer_class(self):
        project = get_object_or_404(Project, pk=self.kwargs['project_id'])
        self.serializer_class = project.get_annotation_serializer()

        return self.serializer_class

    def get_queryset(self):
        document = get_object_or_404(Document, pk=self.kwargs['doc_id'])
        self.queryset = document.get_annotations()

        return self.queryset

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        obj = get_object_or_404(queryset, pk=self.kwargs['annotation_id'])
        self.check_object_permissions(self.request, obj)

        return obj


class RecommendationList(generics.ListCreateAPIView):
    pagination_class = None
    permission_classes = (IsAuthenticated, )

    def get_serializer_class(self):
        project = get_object_or_404(Project, pk=self.kwargs['project_id'])
        self.serializer_class = project.get_recommendation_serializer()

        return self.serializer_class

    def get_queryset(self):
        project = get_object_or_404(Project, pk=self.kwargs['project_id'])
        document = project.documents.get(id=self.kwargs['doc_id'])
        self.queryset = document.get_recommendations()
        self.queryset = self.queryset.filter(user=self.request.user) ##useless trimming needs

        return self.queryset

    def perform_create(self, serializer):
        doc = get_object_or_404(Document, pk=self.kwargs['doc_id'])
        serializer.save(document=doc, user=self.request.user)

    def index_word2char(self, entities, words):
        res = []
        for i in range(len(entities)):
            startOffset = 0
            for j in range(entities[i]['beginOffset']):
                startOffset = startOffset + len(words[j])
                startOffset = startOffset + 1

            endOffset = startOffset

            for j in range(entities[i]['beginOffset'], entities[i]['endOffset']):
                endOffset = endOffset + len(words[j])
                endOffset = endOffset + 1

            endOffset = endOffset - 1

            recommend = {'document': self.kwargs['doc_id'], 'label': entities[i]['type'],
                         'start_offset': startOffset, 'end_offset': endOffset}
            res.append(recommend)
        return res

    def get(self, request, *args, **kwargs):
        project = get_object_or_404(Project, pk=self.kwargs['project_id'])
        document = project.documents.get(id=self.kwargs['doc_id'])
        serializer = self.get_serializer_class()
        global session
        global model
        global graph

        nounchunks = model.noun_chunks(document.text)
        nounchunks_entities = nounchunks['entities']
        nounchunks_words = nounchunks['words']
        chunklist = self.index_word2char(nounchunks_entities, nounchunks_words)

        with session.as_default():
            with graph.as_default():
                response = model.analyze(document.text)
                entities = response['entities']
                words = response['words']
                modellist = self.index_word2char(entities, words)

        for chunk in chunklist:
            for recommend in modellist:
                if chunk['document'] == recommend['document'] and chunk['start_offset'] == recommend['start_offset'] and chunk['end_offset'] == recommend['end_offset']:
                    chunk['label'] = recommend['label']

        serializer = serializer(data=chunklist, many=True)
        if serializer.is_valid():
            serializer.save()
        return Response({"recommendation":chunklist})


class RecommendationDetail(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = (IsAuthenticated, IsOwnAnnotation)

    def get_serializer_class(self):
        project = get_object_or_404(Project, pk=self.kwargs['project_id'])
        self.serializer_class = project.get_recommendation_serializer()

        return self.serializer_class

    def get_queryset(self):
        document = get_object_or_404(Document, pk=self.kwargs['doc_id'])
        self.queryset = document.get_recommendations()

        return self.queryset

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        obj = get_object_or_404(queryset, pk=self.kwargs['annotation_id'])
        self.check_object_permissions(self.request, obj)

        return obj


class LearningInitiate(APIView):
    pagination_class = None
    permission_classes = (IsAuthenticated, IsProjectUser,)

    def get(self, request, *args, **kwargs):
        p = get_object_or_404(Project, pk=self.kwargs['project_id'])
        labels = [label.text for label in p.labels.all()]
        predefined_label = []
        for i in labels:
            predefined_label.append('B-' + str(i))
            predefined_label.append('I-' + str(i))
        predefined_label.append('O')
        docs = [doc for doc in p.documents.all()]
        annotations = [[doc.make_dataset_for_sequence_labeling()] for doc in docs]
        train_docs = [str.split(doc.text) for doc in docs]

        if model.model is None:
            with session.as_default():
                with graph.as_default():
                    model.online_word_build(train_docs, predefined_label)

        response = {'predefined_label': predefined_label,
                    'docs': train_docs,
                    'annotations': annotations}

        return Response(response)


class OnlineLearning(APIView):
    pagination_class = None
    permission_classes = (IsAuthenticated, IsProjectUser)

    def post(self, request, *args, **kwargs):
        p = get_object_or_404(Project, pk=self.kwargs['project_id'])
        labels = [label.text for label in p.labels.all()]
        predefined_label = []
        for i in labels:
            predefined_label.append('B-' + str(i))
            predefined_label.append('I-' + str(i))
        predefined_label.append('O')

        docs_num = request.data.get('indices')
        docs = [doc for doc in p.documents.filter(pk__in=docs_num)]
        annotations = [[label[2] for label in doc.make_dataset_for_sequence_labeling()] for doc in docs]
        train_docs = [str.split(doc.text) for doc in docs]

        if model.model is not None:
            with session.as_default():
                with graph.as_default():
                    model.online_learning(train_docs, annotations, predefined_label)

        response = {'predefined_label': predefined_label,
                    'docs': train_docs,
                    'annotations': annotations}

        return Response(response)